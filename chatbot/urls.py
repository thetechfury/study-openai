from django.urls import path

from chatbot.views import RedirectToUrlView, IndexView, LogoutRedirect, GetGoogleFormsResponses, LogoutPage

urlpatterns = [
    path('redirecting_to_url/', RedirectToUrlView.as_view(), name='redirecting-to-url'),
    path('my_page/', IndexView.as_view(), name='my-page'),
    path('logout_redirect/', LogoutRedirect.as_view(), name='logout-redirect'),
    path('get_form_responses/<str:id>', GetGoogleFormsResponses.as_view(), name='get-form-responses'),
    path('logout', LogoutPage.as_view(), name='logout'),
]
