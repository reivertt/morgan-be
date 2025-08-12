from uuid import uuid4
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from cloudinary_storage.storage import RawMediaCloudinaryStorage
# Example model

class Item(models.Model):
    name = models.CharField(max_length=255)
    price = models.FloatField()

    def __str__(self):
        return self.name
    
class Course(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courses"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

def topic_upload_to(instance, filename):
    """
    Now that we save the file *after* the Topic exists, instance.pk
    will be set and you’ll get exactly:
      user_<uid>/course_<cid>/topic_<tid>/<filename>
    """
    uid = instance.course.owner_id
    cid = instance.course_id
    tid = instance.pk
    ext = filename.rsplit(".", 1)[-1]
    name = uuid4().hex
    return f"user_{uid}/course_{cid}/topic_{tid}/{name}.{ext}"

class Topic(models.Model):
    course     = models.ForeignKey(
        "api.Course", related_name="topics", on_delete=models.CASCADE
    )
    name       = models.CharField(max_length=255)
    file       = models.FileField(
        upload_to=topic_upload_to,
        storage=RawMediaCloudinaryStorage(),
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    progress   = models.IntegerField(default=0)

@receiver(pre_delete, sender=Topic)
def delete_topic_file(sender, instance: Topic, **kwargs):
    if instance.file:
        instance.file.delete(save=False)

@receiver(pre_delete, sender=Course)
def delete_course_topic_files(sender, instance: Course, **kwargs):
    for topic in instance.topics.all():
        if topic.file:
            topic.file.delete(save=False)