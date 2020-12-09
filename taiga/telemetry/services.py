# -*- coding: utf-8 -*-
# Copyright (C) 2014-2017 Andrey Antukh <niwi@niwi.nz>
# Copyright (C) 2014-2017 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014-2017 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014-2017 Alejandro Alonso <alejandro.alonso@kaleidos.net>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import uuid

from django.db.models import Aggregate
from django.db.models import Avg
from django.db.models import Count
from django.db.models import F, Func
from django.db.models import FloatField
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.contrib.contenttypes.models import ContentType

from taiga.projects.history.models import HistoryEntry
from taiga.projects.milestones.models import Milestone
from taiga.projects.models import Project
from taiga.projects.notifications.models import Watched
from taiga.projects.userstories.models import UserStory
from taiga.telemetry.models import InstanceTelemetry
from taiga.users.models import User



class Median(Aggregate):
    function = 'PERCENTILE_CONT'
    name = 'median'
    output_field = FloatField()
    template = '%(function)s(0.5) WITHIN GROUP (ORDER BY %(expressions)s)'

# class RawAnnotation(RawSQL):
#     """
#     RawSQL also aggregates the SQL to the `group by` clause which defeats the purpose of adding it to an Annotation.
#     """
#     def get_group_by_cols(self):
#         return []
# # The Query
# q = MyModel.objects.values('some_fk_id').annotate(
#     avg_duration=Avg('duration'),
#     perc_90_duration=RawAnnotation('percentile_disc(%s) WITHIN GROUP (ORDER BY duration)', (0.9,)),
# )



def get_or_create_instance_info():
    instance = InstanceTelemetry.objects.first()
    if not instance:
        instance = InstanceTelemetry.objects.create(
            instance_id=uuid.uuid4().hex
        )

    return instance


def generate_platform_data():
    total_uss = UserStory.objects.count()

    pd = {}

    # number of projects
    pd['tt_projects'] = Project.objects.count()

    # number of private projects
    pd['tt_projects_private'] = Project.objects.filter(
            is_private=True
        ).count(),

    # number of public projects
    pd['tt_projects_public'] = Project.objects.filter(
            is_private=False
        ).count()

    # number of projects with scrum active and kanban inactive
    pd['tt_projects_only_scrum'] = Project.objects.filter(
            is_backlog_activated=True, is_kanban_activated=False
        ).count()

    # number of projects with both scrum and kanban active
    pd['tt_projects_kanban_scrum'] = Project.objects.filter(
            is_backlog_activated=True, is_kanban_activated=True
        ).count()

    # number of projects with none scrum and kanban active
    pd['tt_projects_no_kanban_no_scrum'] = Project.objects.filter(
            is_backlog_activated=False, is_kanban_activated=False
        ).count()

    # number of projects with kaban active and scrum inactive
    pd['tt_projects_only_kanban'] = Project.objects.filter(
            is_backlog_activated=False, is_kanban_activated=True
        ).count()

    # number of projects with kaban active and at least 1 swimlane
    pd['tt_projects_swimlanes_active_kanban'] = Project.objects.annotate(
            total_swimlanes=Count('swimlanes')
        ).filter(
            total_swimlanes__gte=1, is_kanban_activated=True
        ).count()

    # number of projects with issues active
    pd['tt_projects_issues'] = Project.objects.filter(
            is_issues_activated=True
        ).count()

    # number of projects with epics active
    pd['tt_projects_epics'] = Project.objects.filter(
            is_epics_activated=True
        ).count()

    # number of projects with wiki active
    pd['tt_projects_wiki'] = Project.objects.filter(
            is_wiki_activated=True
        ).count()

    # number of projects with at least 1 tag
    pd['tt_projects_tags'] = 'TODO'

    # number of projects with at least 1 custom field
    pd['tt_projects_custom_fields'] = Project.objects.annotate(
            total_custom_fields=Count('epiccustomattributes', distinct=True) + \
                                Count('issuecustomattributes', distinct=True) + \
                                Count('taskcustomattributes', distinct=True) + \
                                Count('userstorycustomattributes', distinct=True)
        ).exclude(
            total_custom_fields=0
        ).count()

    # number of users
    pd['tt_users'] = User.objects.count()

    # number of active users
    pd['tt_users_active'] = User.objects.filter(
            is_active=True
        ).count()

    # average and median of epics in projects with module epics active
    epics = Project.objects.filter(
            is_epics_activated=True
        ).annotate(
            total_epics=Count('epics')
        ).aggregate(
            avg_epics_project=Avg('total_epics'),
            median_epics=Median('total_epics')
        )
    pd['tt_avg_epics_project'] = epics['avg_epics_project']
    pd['tt_median_epics']  = epics['median_epics']

    # average and median of userstories in projects with module scrum or kanban active
    userstories = Project.objects.filter(
            Q(is_kanban_activated=True) | Q(is_backlog_activated=True)
        ).annotate(
            total_user_stories=Count('user_stories')
        ).aggregate(
            avg_uss_project=Avg('total_user_stories'),
            median_userstories=Median('total_user_stories')
        )
    pd['tt_avg_uss_project'] = userstories['avg_uss_project']
    pd['tt_median_userstories'] = userstories['median_userstories']

    # average and of issues in projects with module issues active
    issues = Project.objects.filter(
            is_issues_activated=True
        ).annotate(
            total_issues=Count('issues')
        ).aggregate(
            avg_issues_project=Avg('total_issues'),
            median_issues=Median('total_issues')
        )
    pd['tt_avg_issues_project'] = issues['avg_issues_project']
    pd['tt_median_issues'] = issues['median_issues']

    # average and of swimlanes in projects with kanban
    swimlanes = Project.objects.annotate(
            total_swimlanes=Count('swimlanes')
        ).filter(
            is_kanban_activated=True
        ).aggregate(
            avg_swimlanes_project=Avg('total_swimlanes'),
            median_swimlanes=Median('total_swimlanes')
        )
    pd['tt_avg_swimlanes_project'] = swimlanes['avg_swimlanes_project']
    pd['tt_median_swimlanes'] = swimlanes['median_swimlanes']

    # average and median of tags in projects with at least one tag
    tags = Project.objects.annotate(
            total_tags=Func(F('tags_colors'), 1, function='array_length')
        ).aggregate(
            avg_tags_project=Avg('total_tags'),
            median_tags=Median('total_tags')
        )
    pd['tt_avg_tags_project'] = tags['avg_tags_project']
    pd['tt_median_tags'] = tags['median_tags']

    # average and median of custom fields in projects with at least 1 custom field
    custom_fields = Project.objects.annotate(
            total_custom_fields=Count('epiccustomattributes', distinct=True) + \
                                Count('issuecustomattributes', distinct=True) + \
                                Count('taskcustomattributes', distinct=True) + \
                                Count('userstorycustomattributes', distinct=True)
        ).exclude(
            total_custom_fields=0
        ).aggregate(
            avg_custom_fields_project=Avg('total_custom_fields'),
            median_custom_fields=Median('total_custom_fields')
        )
    pd['tt_median_custom_fields'] = custom_fields['avg_custom_fields_project']
    pd['tt_avg_custom_fields_project'] = custom_fields['median_custom_fields']

    # average and median of members per project
    members = Project.objects.annotate(
            total_members=Count('members')
        ).aggregate(
            avg_members_project=Avg('total_members'),
            median_members=Median('total_members')
        )
    pd['tt_avg_members_project'] = members['avg_members_project']
    pd['tt_median_members'] = members['median_members']

    # average and median of roles per project
    roles = Project.objects.annotate(
            total_roles=Count('roles')
        ).aggregate(
            avg_roles_project=Avg('total_roles'),
            median_roles=Avg('total_roles')
        )
    pd['tt_avg_roles_project'] = roles['avg_roles_project']
    pd['tt_median_roles'] = roles['median_roles']

    # percent of user stories assigned
    pd['tt_percent_uss_assigned'] = _get_tt_percent_uss_assigned(total_uss)

    # percent of user stories watched
    pd['tt_percent_uss_watching'] = _get_tt_percent_uss_watched(total_uss)

    # percent of user stories with at least one comment
    pd['tt_percent_uss_comments_gte_1'] = HistoryEntry.objects.filter(
            key__startswith='userstories.userstory:',
            comment__isnull=False
        ).order_by(
            'key'
        ).distinct(
            'key'
        ).count()

    # average and median of sprints in projects with backlog activated
    sprints = Project.objects.annotate(
            total_sprints=Count('milestones')
        ).filter(
            is_backlog_activated=True
        ).aggregate(
            avg_sprints_project=Avg('total_sprints'),
            median_sprints=Avg('total_sprints')
        )
    pd['tt_avg_sprints_project'] = sprints['avg_sprints_project']
    pd['tt_median_sprints'] = sprints['median_sprints']

    # average of uss per sprint
    uss_sprint = Milestone.objects.annotate(
            total_user_stories=Count('user_stories')
        ).aggregate(
            avg_uss_sprint=Avg('total_user_stories'),
            median_uss_sprint=Avg('total_user_stories')
        )
    pd['tt_avg_uss_sprint'] = uss_sprint['avg_uss_sprint']
    pd['tt_median_uss_sprint'] = uss_sprint['median_uss_sprint']

    # number of edits
    pd['tt_edits_today'] = HistoryEntry.objects.filter(
            created_at__day=datetime.datetime.today().day
        ).count()

    # number of new US
    pd['tt_new_user_stories_today'] = UserStory.objects.filter(
            created_date__day=datetime.datetime.today().day
        ).count()

    # number of closed US
    pd['tt_finished_user_stories_today'] = UserStory.objects.filter(
            finish_date__day=datetime.datetime.today().day
        ).count()

    return pd


def generate_system_data():
    system_data = {
        'version': '6.0.0'
    }

    return system_data


def _get_tt_percent_uss_assigned(total_uss):
    assigned_uss = UserStory.objects.filter(assigned_users__isnull=False).count()
    return assigned_uss * 100 / total_uss


def _get_tt_percent_uss_watched(total_uss):
    content_type = ContentType.objects.get(model='userstory')
    watched_uss = Watched.objects.filter(content_type=content_type).distinct('object_id').count()
    return watched_uss * 100 / total_uss
