from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from study_openai import settings

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path('', include('chatbot.urls')),
                  path('accounts/', include('allauth.urls')),
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
