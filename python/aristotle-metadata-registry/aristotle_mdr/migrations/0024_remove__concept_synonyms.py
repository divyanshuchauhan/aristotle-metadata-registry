# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-04-03 23:44
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0023_auto_20180206_0332'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='_concept',
            name='synonyms',
        ),
    ]
