import pmxbot
from pmxbot.core import command

from pagerduty.api import PagerDutyAPI
import pagerduty.api as api


slack_name_pd_id_map = pmxbot.config['pagerduty']['users']
pd_api = PagerDutyAPI(pmxbot.config['pagerduty']['token'])


def _user_by_name(uname):
    """Resolve a slack username to a PagerDuty user ID"""
    uid = slack_name_pd_id_map.get(uname)
    if not uid:
        raise RuntimeError("Couldn't resolve user name: {}".format(uname))

    return uid


def _format_incident_for_display(incident):
    incident_tpl = '- {created_at} {title}: {status} --- {description}'
    return incident_tpl.format(**incident)


@command(aliases='dr')
def damage_report(nick):
    msg_tpl = """
Damage Report:
{}
"""
    uid = _user_by_name(nick)
    incidents = api.incidents_by_user(uid)
    formatted_incidents = [_format_incident_for_display(i) for i in incidents['incidents']]
    if formatted_incidents:
        return msg_tpl.format('\n'.join(formatted_incidents))
    else:
        return 'All clear.'


@command(aliases='ack')
def ack(nick, rest):
    return 'YOU CALLED?'
