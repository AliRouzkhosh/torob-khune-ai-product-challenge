from django.db import models


class Listing(models.Model):
    @property
    def neighborhood_display(self):
        from .location_registry import display_location
        return display_location(self.neighborhood)

    data_source = models.CharField(max_length=12, default='synthetic', db_index=True)
    source_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    source_metadata = models.JSONField(default=dict)
    city = models.CharField(max_length=60, default='tehran')
    title = models.CharField(max_length=150)
    neighborhood = models.CharField(max_length=80, blank=True, db_index=True)
    description = models.TextField()
    deposit = models.PositiveBigIntegerField()
    monthly_rent = models.PositiveBigIntegerField()
    alternative_deposit = models.PositiveBigIntegerField(null=True, blank=True)
    alternative_rent = models.PositiveBigIntegerField(null=True, blank=True)
    area_m2 = models.PositiveIntegerField()
    bedrooms = models.PositiveSmallIntegerField(db_index=True)
    floor = models.SmallIntegerField(null=True, blank=True)
    construction_year = models.PositiveSmallIntegerField(null=True, blank=True)
    renovated = models.BooleanField(null=True, default=None)
    renovation_claim = models.BooleanField(null=True, default=None)
    parking = models.BooleanField(null=True, default=None)
    elevator = models.BooleanField(null=True, default=None)
    storage = models.BooleanField(null=True, default=None)
    balcony = models.BooleanField(null=True, default=None)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_radius_m = models.FloatField(null=True, blank=True)
    distance_to_work_km = models.FloatField(null=True, blank=True)
    distances = models.JSONField(default=dict)
    natural_light = models.FloatField(null=True, default=None)
    quietness = models.FloatField(null=True, default=None)
    layout_quality = models.FloatField(null=True, default=None)
    access_quality = models.FloatField(null=True, default=None)
    evidence = models.JSONField(default=list)
    data_conflicts = models.JSONField(default=list)
    image_name = models.CharField(max_length=40)
