from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models, transaction
from django.db.models.functions import Lower, Trim
from django.db.models.signals import post_delete
from django.dispatch import receiver


def category_photo_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"categories/{uuid4().hex}.{extension}"


class CategoryQuerySet(models.QuerySet):
    def parents(self):
        return self.alias(
            is_used_as_parent=models.Exists(
                self.model.objects.filter(parent_id=models.OuterRef("pk"))
            )
        ).filter(models.Q(is_parent_category=True) | models.Q(is_used_as_parent=True))

    def delete(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734003004)")
            return super().delete()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_parent_category = models.BooleanField(default=False, editable=False)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    position = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    is_active = models.BooleanField(default=True)

    photo = models.ImageField(upload_to=category_photo_path, blank=True)
    photo_x = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    photo_y = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    photo_zoom = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(100), MaxValueValidator(200)],
        help_text="100 to 200 percent.",
    )

    objects = CategoryQuerySet.as_manager()

    class Meta:
        ordering = ["position", "name", "pk"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(Lower(Trim("name")), name="category_name_normalized_unique"),
            models.CheckConstraint(condition=~models.Q(name=""), name="category_name_not_empty"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a category name."})
        duplicates = Category.objects.filter(name__iexact=self.name).exclude(pk=self.pk)
        if duplicates.exists():
            raise ValidationError({"name": "A category with this name already exists."})
        seen = {self.pk} if self.pk else set()
        ancestor_id = self.parent_id
        while ancestor_id is not None:
            if ancestor_id in seen:
                raise ValidationError(
                    {"parent": "A category cannot contain itself or an ancestor."}
                )
            seen.add(ancestor_id)
            ancestor_id = (
                Category.objects.filter(pk=ancestor_id).values_list("parent_id", flat=True).first()
            )

    def save(self, *args, **kwargs):
        # Serialize hierarchy validation so concurrent reparenting cannot create a cycle.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734003004)")
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734003004)")
            return super().delete(*args, **kwargs)


@receiver(post_delete, sender=Category)
def delete_category_photo(sender, instance, using, **kwargs):
    if instance.photo:
        storage, name = instance.photo.storage, instance.photo.name
        transaction.on_commit(lambda: storage.delete(name), using=using)
