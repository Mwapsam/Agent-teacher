from django.db import models


class LessonPlan(models.Model):
    teacher_name = models.CharField(max_length=100)
    date = models.DateField()
    school = models.CharField(max_length=100)
    time = models.CharField(max_length=20)
    grade = models.CharField(max_length=10)
    duration = models.CharField(max_length=20)
    subject = models.CharField(max_length=50)
    num_pupils = models.IntegerField()
    topic = models.CharField(max_length=100)
    sub_topic = models.CharField(max_length=100)
    gender = models.CharField(max_length=20)
    objectives = models.TextField()
    teaching_materials = models.TextField()
    reference_materials = models.TextField()
    introduction = models.TextField()
    lesson_development = models.TextField()
    conclusion = models.TextField()
    recapitulation = models.TextField()
    evaluation = models.TextField()
    teacher_evaluation = models.TextField()
    homework = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sub_topic} - {self.date}"
