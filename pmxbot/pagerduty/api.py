import logging
import os
from datetime import datetime, timedelta

import requests as r

log = logging.getLogger(__name__)
refresh_delta = timedelta(hours=1)

# Known Endpoints:
# - incidents
# - users
# - escalation_policies

# Not working:
# - team(s) -- turns out the teams endpoint captures a thing we don't use.


# !ack: Acknowledges all incidents assigned to the ack-ing user. (I.E. if I have three open incidents, and someone else has two, my !ack only acks my three incidents.)
# !ack <id>: acknowledges a specific incident
# !resolve: Resolve all incidents assigned to the resolving user.
# !resolve <id>: Resolve incident by id
# !damage-report: list all open incidents for the calling user's team
# !tell-oncall <team>: <message> Send a slack <message> to the current primary oncall of <team>
# !page <team>: <message>: Open a new incident titled <message> and assign it to current primary oncall for <team>

class PagerDutyAPI():
    _slack_name_pd_id_map = {}  # pmxbot.config['pagerduty']['users']

    _REST_API_URL = 'https://api.pagerduty.com'
    _EVENTS_API_URL = 'https://events.pagerduty.com/v2/enqueue'

    users_endpoint = 'users'
    incidents_endpoint = 'incidents'

    incident_triggered_status = 'triggered'
    incident_ackd_status = 'acknowledged'
    incident_resolved_status = 'resolved'

    escalation_endpoint = 'escalation_policies'

    def __init__(self, pd_api_key, name_map):
        self._api_key = pd_api_key
        self._slack_name_pd_id_map = name_map
        self.incident_active_statuses = [
            self.incident_triggered_status,
            self.incident_ackd_status,
        ]
        self.incident_inacvitve_statuses = [self.incident_resolved_status]

    def _call_pd_api(self, endpoint, method, data={}, query_params={}, extra_headers={}):
        url = os.path.join(self._REST_API_URL, endpoint)

        headers = {
            'Accept': 'application/vnd.pagerduty+json;version=2',
            'Authorization': 'Token token=' + self._api_key,
            **extra_headers,
        }

        res = method(
            url,
            headers=headers,
            json=data,
            params=query_params
        )

        if res.status_code >= 400:
            log.error(res.status_code)
            log.error(res.reason)
            # raise RuntimeError('Something has happened, oh no')
            return res

        return res.json()

    def _api_get(self, endpoint, query_params={}):
        return self._call_pd_api(endpoint, r.get, query_params=query_params)

    def _api_put(self, endpoint, payload={}, query_params={}, extra_headers={}):
        return self._call_pd_api(
            endpoint,
            r.put,
            data=payload,
            query_params=query_params,
            extra_headers=extra_headers
        )

    def _join(self, *args):
        return os.path.join(*[str(arg) for arg in args])

    def user_by_name(self, uname):
        uid = self._slack_name_pd_id_map.get(uname)
        if not uid:
            raise RuntimeError("Couldn't resolve user name: {}".format(uname))

        return self.user_by_id(uid)

    def user_by_id(self, uid):
        endpoint = self._join(self.users_endpoint, uid)

        return self._api_get(endpoint)

    def users(self):
        endpoint = self.users_endpoint
        return self._api_get(endpoint)

    def incident_by_id(self, inc_id):
        endpoint = self._join(self.incidents_endpoint, inc_id)
        return self._api_get(endpoint)

    def incidents_list(self, statuses=None):
        statuses = statuses or self.incident_active_statuses
        params = {
            'statuses[]': statuses
        }
        endpoint = self.incidents_endpoint
        return self._api_get(endpoint, params)

    def incidents_by_user(self, uid, statuses=[]):
        statuses = statuses or self.incident_active_statuses
        params = {
            'user_ids[]': [uid],
            'statuses[]': statuses,
        }
        endpoint = self.incidents_endpoint
        return self._api_get(endpoint, params)

    def incidents_ack(self, acking_email: str, to_ack: list):
        endpoint = self.incidents_endpoint
        headers = {'from': acking_email}
        incidents = [
            {'id': inc_id, 'status': 'acknowledged', 'type': 'incident'}
            for inc_id in to_ack
        ]

        return self._api_put(
            endpoint,
            payload={'incidents': incidents},
            extra_headers=headers
        )


class PagerDutyResponse:
    pass


pd_ids_to_emails = {}


def get_email_for_user(uid):
    """
    Surreal, but true: you can't ack an event by PagerDuty ID. You must use the
    email on file. Neat.
    """
    # There's a chance we've already loaded and stored this email before.
    maybe_email, last_checked = pd_ids_to_emails.get(uid, (None, None))
    this_instant = datetime.now()

    if maybe_email:
        if (this_instant - last_checked) < refresh_delta:
            # Email fresh enough, don't re-check
            return maybe_email

    api = PagerDutyAPI()
    try:
        user_json = api.user_by_id(uid)
    except RuntimeError:
        log.error("Couldn't load an email address for user with id: ", uid)
        return

    found_email = user_json['user']['email']

    # Cache the email, along with when we retrieved it
    pd_ids_to_emails[uid] = (found_email, this_instant)

    return found_email


def get_incident_ids(incidents):
    """Parses the ID property from a set of incidents."""
    return [i['id'] for i in incidents['incidents']]


def ack(uid, to_ack=None):
    api = PagerDutyAPI()
    ack_from = get_email_for_user(uid)

    if not to_ack:
        incidents = api.incidents_by_user(uid, statuses=[api.incident_triggered_status])
        to_ack = get_incident_ids(incidents)

    return api.incidents_ack(ack_from, to_ack)


def resolve(incident_id):
    pass


def damage_report(uid):
    api = PagerDutyAPI()
    return api.incidents_by_user(uid)


def page():
    pass


def tell():
    pass
