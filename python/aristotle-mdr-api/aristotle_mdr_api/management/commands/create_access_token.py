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

class Command(BaseCommand):
    args = ''
    help = 'Creates a access token for API'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        # parser.add_argument(
        #     "--noinput",
        #     default=False,
        #     action='store_true',
        # )

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

        client = Client()
        client.post(reverse('logout'), {})
        response = client.post(reverse('friendly_login'), {'username': 'admin@myproject.com', 'password': 'password'})
        postdata = {'name': 'div', 'perm_json': json.dumps(all_true_perms)}
        response = client.post('0.0.0.0:8080/api/token/create/', postdata)
        return response.context_data['key']
