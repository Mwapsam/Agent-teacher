from django.urls import path
from lesson_plan.views import create_lesson_plan, generate_and_save_lesson_plan

urlpatterns = [
    path("", generate_and_save_lesson_plan, name="create_lesson_plan"),
]
