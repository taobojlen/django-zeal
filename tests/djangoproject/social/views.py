from django.http import HttpRequest, JsonResponse

from .models import User


def single_user_and_profile(request: HttpRequest, id: int):
    user = User.objects.get(id=id)
    return JsonResponse(
        data={
            "username": user.username,
            "display_name": user.profile.display_name,
        }
    )


def all_users_and_profiles(request: HttpRequest):
    """
    This view has an N+1.
    """
    return JsonResponse(
        data={
            "users": [
                {
                    "username": user.username,
                    "display_name": user.profile.display_name,
                }
                for user in User.objects.all()
            ]
        }
    )
