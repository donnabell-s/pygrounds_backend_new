from django.contrib import admin
from django.apps import apps

Model = None
for model_name in ("GeneratedQuestion", "Question"):
    try:
        Model = apps.get_model("question_generation", model_name)
        if Model:
            break
    except LookupError:
        continue

# Register only if we actually found a suitable model
if Model:
    admin.site.register(Model)