from django.urls import path

from .social.views import all_users_and_profiles, single_user_and_profile

urlpatterns = [
    path("users/", all_users_and_profiles),
    path("user/<int:id>/", single_user_and_profile),
]
