from django.db import models
from django.contrib.auth.models import User


class TestResult(models.Model):
	"""Stores saved test results for a user as JSON payloads."""
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_results')
	payload = models.JSONField(null=True, blank=True)
	summary = models.JSONField(null=True, blank=True)
	saved_at = models.DateTimeField(auto_now_add=True)

	# Friendly fields for quick listing / UI
	dtw_score = models.FloatField(null=True, blank=True)
	final_score = models.FloatField(null=True, blank=True)
	stgcn_score = models.FloatField(null=True, blank=True)
	ai_verdict = models.TextField(null=True, blank=True)
	deep_verdict = models.TextField(null=True, blank=True)
	windows = models.JSONField(null=True, blank=True)
	window_count = models.IntegerField(null=True, blank=True)
	ref_job_id = models.CharField(max_length=128, null=True, blank=True)
	user_job_id = models.CharField(max_length=128, null=True, blank=True)
	compare_job_id = models.CharField(max_length=128, null=True, blank=True)

	class Meta:
		ordering = ['-saved_at']

	def __str__(self):
		return f"TestResult {self.pk} by {self.user.username} at {self.saved_at}"
