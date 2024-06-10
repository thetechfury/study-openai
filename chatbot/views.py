import json
import os
import pickle

import numpy as np
import openai
from allauth.socialaccount.models import SocialToken, SocialApp
from bson import Binary
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_core.documents import Document
from langdetect import detect
from pymongo import MongoClient
from study_openai import settings
from study_openai.settings import MEDIA_ROOT, STATICFILES_DIRS


class RedirectToUrlView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return render(request, 'redirecting_url.html')
        else:
            return render(request, '404.html')


class IndexView(View):

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            response = self.get_forms(request)
            return render(request, 'sigin_google.html', context={'data': response})
        return render(request, 'sigin_google.html')

    def get_forms(self, request):
        try:
            # Fetching Google token and app for the user
            token = SocialToken.objects.get(account__user=request.user, account__provider='google')
            app = SocialApp.objects.get(provider='google')

            # Creating credentials
            credentials = Credentials(
                token=token.token,
                refresh_token=token.token_secret,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=app.client_id,
                client_secret=app.secret
            )

            # Building Google Drive service
            drive_service = build('drive', 'v3', credentials=credentials)

            # Listing Google Drive files of type application/vnd.google-apps.form
            page_token = None
            while True:
                response = drive_service.files().list(
                    q="mimeType='application/vnd.google-apps.form'",
                    spaces='drive',
                    fields='nextPageToken, files(id, name)',
                    pageToken=page_token
                ).execute()
                return response.get('files', [])
        except SocialToken.DoesNotExist:
            print("Social token not found for the user.")
        except HttpError as error:
            if error.resp.status == 403:
                print("Insufficient permission error:", error)
            else:
                print("An error occurred:", error)
        except RefreshError as e:
            logout(request)


class LogoutPage(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('my-page')


class GetGoogleFormsResponses(View):

    def get(self, request, *args, **kwargs):
        form_id = kwargs.get('id')
        form_info, response = self.get_form_details(request, form_id)
        if response:
            form_responses = response.get('responses', None)
            items_list = self.get_form_items(form_info)
            response_list = self.get_responses_list(form_responses, items_list)
            json_data = json.dumps(response_list)
            self.main(request, json_data, form_id)
            return render(request, 'forms_respnses.html', context={'responses': response_list, 'form_id': form_id})
        else:
            return render(request, 'forms_respnses.html', context={'responses': 'Error getting responses.'})

    def main(self, request, json_data, form_id):

        # Set OpenAI API key
        openai.api_key = settings.OPENAI_API_KEY

        # Connect to MongoDB
        client = MongoClient(settings.MONGODB_URI)
        db = client["vector_db"]
        collection = db[form_id]

        documents = [Document(page_content=self.make_string_from_object_list(item['answers']),
                              metadata={"source": form_id})
                     for item in json.loads(json_data)]
        # Create OpenAI embeddings
        embeddings = OpenAIEmbeddings()

        # Store documents and embeddings in MongoDB
        for doc in documents:
            # Check if the document content already exists in the database
            existing_doc = collection.find_one({"content": doc.page_content})
            if existing_doc:
                continue

            # Compute the embedding for the document
            embedding_vector = embeddings.embed_query(doc.page_content)
            doc_dict = {
                "content": doc.page_content,
                "embedding": Binary(pickle.dumps(embedding_vector, protocol=2))
            }
            collection.insert_one(doc_dict)

    def post(self, request, *args, **kwargs):
        form_id = kwargs.get('id')
        query = request.POST.get('query')
        if query:
            # Reinitialize embeddings
            openai.api_key = settings.OPENAI_API_KEY
            embeddings = OpenAIEmbeddings()
            client = MongoClient(settings.MONGODB_URI)
            db = client["vector_db"]
            collection = db[form_id]

            query_language = detect(query)

            # Read instructions from file
            instruction_file_path = os.path.join(STATICFILES_DIRS[0], 'instructions_file/openai_instructions.txt')
            with open(instruction_file_path, 'r') as file:
                instructions = file.read().format(query_language=query_language)

            # Embed the user query
            query_embedding = embeddings.embed_query(query)

            # Retrieve stored embeddings from MongoDB
            stored_docs = list(collection.find())

            # Calculate similarity with stored embeddings
            def cosine_similarity(vec1, vec2):
                return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

            similarities = [
                (doc, cosine_similarity(query_embedding, pickle.loads(doc["embedding"])))
                for doc in stored_docs
            ]

            similarities.sort(key=lambda x: x[1], reverse=True)

            # Combine content from the top N documents for context
            related_content = "\n\n".join([doc[0]["content"] for doc in similarities[:6]])

            # Combine related content with the user query for context
            combined_input = f"User: {query}\n\nContext from data: {related_content}"

            # Call OpenAI API to get response
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": combined_input}
                ]
            )

            # Add bot response to session state
            bot_response = response.choices[0].message.content
            return JsonResponse({'bot_response': bot_response})

    def get_form_items(self, form_info):
        items_list = []
        for item in form_info['items']:
            question_id = item['questionItem']['question']['questionId']
            title = item['title']
            image_url = None
            if 'image' in item['questionItem']:
                image_url = item['questionItem']['image']['contentUri']
            items_list.append({
                'question_id': question_id,
                'title': title,
                'image_url': image_url
            })
        return items_list

    def get_responses_list(self, form_responses, items_list):
        response_list = []
        for resp in form_responses:
            response_dict = {
                'response_id': resp['responseId'],
                'create_time': resp['createTime'],
                'last_submitted_time': resp['lastSubmittedTime'],
                'answers': []
            }
            for key, value in resp['answers'].items():
                question_id = key
                title = None
                image_url = None
                for item in items_list:
                    if item['question_id'] == question_id:
                        title = item['title']
                        if item['image_url']:
                            image_url = item['image_url']

                if 'fileUploadAnswers' in value:
                    ans = value['fileUploadAnswers']['answers']
                else:
                    ans = value['textAnswers']['answers']

                response_dict['answers'].append({
                    'question_id': question_id,
                    'title': title,
                    'value': ans,
                    'image': image_url,
                })
            response_list.append(response_dict)
        return response_list

    def get_form_details(self, request, form_id):
        try:
            # Fetching Google token and app for the user
            token = SocialToken.objects.get(account__user=request.user, account__provider='google')
            app = SocialApp.objects.get(provider='google')

            # Creating credentials
            credentials = Credentials(
                token=token.token,
                refresh_token=token.token_secret,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=app.client_id,
                client_secret=app.secret
            )

            # Building Google Drive service
            form_service = build('forms', 'v1', credentials=credentials)
            forms = form_service.forms()
            form_details = forms.get(formId=form_id).execute()
            form_responses = forms.responses().list(formId=form_id).execute()
            return form_details, form_responses
        except SocialToken.DoesNotExist:
            print("Social token not found for the user.")
        except HttpError as error:
            if error.resp.status == 403:
                print("Insufficient permission error:", error)
            else:
                print("An error occurred:", error)
        except RefreshError as e:
            logout(request)

    def write_json_to_file(self, json_data, filename):
        file_path = os.path.join(MEDIA_ROOT, filename)
        with open(file_path, 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
        return file_path

    def read_json_from_file(self, filename):
        file_path = os.path.join(MEDIA_ROOT, filename)
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
        return data

    def make_string_from_object_list(self, data):
        result_strings = []
        for item in data:
            title = item['title']
            value = item['value'][0].get('value', None)
            # image = item['value'][0].get('image', None)

            if not value:
                file_id = item['value'][0]['fileId']
                file_name = item['value'][0]['fileId']
                file_type = item['value'][0]['fileId']
                result_strings.append(f"{file_type}: {file_name} has file_id {file_id}")
            # elif image:
            #     result_strings.append(f"{title}: {image}")
            else:
                result_strings.append(f"{title}: {value}")
        final_string = "\n".join(result_strings)
        return final_string


class LogoutRedirect(TemplateView):
    template_name = 'redirecting_url.html'
