from django.conf.urls import include, url
from rest_framework.documentation import include_docs_urls
from rest_framework_swagger.views import get_swagger_view
from django.utils.module_loading import import_string
from .views import APIRootView
# from rest_framework.authtoken import views as tokenviews

import re

API_TITLE = 'Aristotle MDR API'
API_DESCRIPTION = """
---

The Aristotle Metadata Registry API is a standardised way to access metadata through a consistent
machine-readable interface.

"""

def version_schema(*args, **kwargs):
    version = kwargs.pop('version')
    if version:
        patterns = import_string('aristotle_mdr_api.%s.urls.urlpatterns' % version)
    else:
        patterns = []

    return get_swagger_view(
            title='Aristotle API %s' % version,
            patterns=patterns
        )(*args)


urlpatterns = [
    url(r'^auth/', include('rest_framework.urls', namespace='rest_framework')),
    # url(r'^api-token-auth/', tokenviews.obtain_auth_token),
    url(r'^token/', include('aristotle_mdr_api.token_auth.urls', namespace='token_auth')),
    url(r'^(?P<version>(v2|v3)?)/schemas/', version_schema),
    url(r'^schemas/', get_swagger_view(title='Aristotle API')),
    url(r'^$', APIRootView.as_view(), name="aristotle_api_root"),

    url(r'^v2/', include('aristotle_mdr_api.v2.urls', namespace='aristotle_mdr_api.v2')),
    url(r'^v3/', include('aristotle_mdr_api.v3.urls', namespace='aristotle_mdr_api.v3')),
    url(r'^v3.1/', include('aristotle_mdr_api.v3_1.urls', namespace='aristotle_mdr_api.v3_1')),
]
