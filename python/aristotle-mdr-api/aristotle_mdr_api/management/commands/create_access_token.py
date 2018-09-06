import os
from tempfile import mkdtemp

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from django.test import override_settings

from django.test import TestCase, Client, override_settings, tag
from aristotle_mdr_api.token_auth.models import AristotleToken
import json
from django.urls import reverse
import static_precompiler
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    args = ''
    help = 'Creates a access token for API'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        all_true_perms =  {
            'metadata': {
                'read': True,
                'write': True
            },
            'search': {
                'read': True
            },
            'organization': {
                'read': True
            },
            'ra': {
                'read': True
            }
        }

        user = get_user_model().objects.get(email='admin@myproject.com')
        token = AristotleToken.objects.create(
            name='name',
            user=user,
            permissions=all_true_perms
        )
        return token.key
        


