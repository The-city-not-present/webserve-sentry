
# import uuid
import secrets
import redis

from typing import Any
from datetime import datetime, timedelta
from dataclasses import dataclass


from .common_defs import RequestToSentry, ContextForSentry

from .session_storage import SessionStorage
from .visitor_storage import VisitorStorage
from .user_storage import UserStorage


# TODO:
#     # 8. - defensive anti-bot protections (hidden fields, and similar
#     # 9. - get more info on Content-Security-Policy (CSP) → prevents XSS, Strict-Transport-Security (HSTS) → forces HTTPS, X-Frame-Options → prevents clickjacking, X-Content-Type-Options → prevents MIME sniffing)
#     # - set JWT ???



class SentryReject(Exception):
    """Acts as HTTP 401"""


# tuples of interval name, duration in seconds, and dict with tresholds
TIMINGS_INTERVALS = [
    (
        '1h',
        3600,
        {
            'ip': 4000,
            'newsessionsperip': 15,
            'sessionid': 400,
            'visitorid': 400,
            'userid': 400,
        },
    ),
    (
        '10m',
        600,
        {
            'ip': 1800,
            'newsessionsperip': 8,
            'sessionid': 180,
            'visitorid': 180,
            'userid': 180,
        },
    ),
    (
        '2m',
        120,
        {
            'ip': 1100,
            'newsessionsperip': 7,
            'sessionid': 110,
            'visitorid': 110,
            'userid': 110,
        },
    ),
    (
        '30s',
        30,
        {
            'ip': 400,
            'newsessionsperip': 6,
            'sessionid': 40,
            'visitorid': 40,
            'userid': 40,
        },
    ),
    (
        '10s',
        10,
        {
            'ip': 190,
            'newsessionsperip': 5,
            'sessionid': 19,
            'visitorid': 19,
            'userid': 19,
        },
    ),
]
MAX_TIMINGCOUNTER_RECORDS_PULL = 10000
MAX_TIMINGCOUNTER_AGE_PULL = 600
MAX_TIMINGCOUNTER_AGE_SESSIONPERIP_PULL = 7200


@dataclass(frozen=True)
class ContextForSentryProcess:
    redis: Any
    session_storage: Any
    visitor_storage: Any
    user_storage: Any

class SentryRecord:
    """
    Session id should not break/invalidate on ip changes
    It must break/invalidate on device/ua change
    """
    def __init__(
        self,
        context: ContextForSentryProcess,
        request: RequestToSentry,
    ):
        self.context = context
        self.request = request
        self.response = {}

        # 1. - grab ip
        # 1.1. - - possibly ip type
        # 1.2. - - possibly geo mismatch
        self.response = {**self.response,**self.assign_ipinfo()}

        # 2. - possibly other cookies
        self.response = {**self.response,**self.assign_cookieinvestigationinfo()}

        # 3. - user-agent
        # 3.1. - - mobile-non-mobile
        # 3.2. - - so, implement device fingerprinting
        self.response = {**self.response,**self.assign_deviceinfo()}

        # 4. - Accept, Accept-Language, Accept-Encoding
        self.response = {**self.response,**self.assign_langprefinfo()}

        # 5. - TZ info
        self.response = {**self.response,**self.assign_tzinfo()}

        self.debug_log(metric='headers/cookies/sessionid')
        # is existing session?
        self.response = {**self.response,**self.assign_sessionid()}

        # is existing visitor?
        self.response = {**self.response,**self.assign_visitorid()}

        # is existing user?
        self.response = {**self.response,**self.assign_userid()}

        # 6. - request timing!!! counters! The most important
        self.response = {**self.response,**self.assign_ratelimitinfo()}

        # 7. - imlement "risk-scoring"
        self.response = {**self.response,**self.assign_riskscoringinfo()}

    def debug_log(self,metric,event_data=None):
        def print_headers_cookies_sessionid():
            print('DEBUG: sentry: start headers')
            print(self.request.headers)
            print('DEBUG: sentry: end headers')
            print('DEBUG: sentry: start cookies')
            for morsel in self.request.cookies.values():
                print(morsel.OutputString())
            print('DEBUG: sentry: end cookies')
        def print_sessionid_generated():
            print(f'DEBUG: sentry: sessionid not found, generated new: {event_data.get("sessionid")}')
        def print_sessionid_found():
            print(f'DEBUG: sentry: sessionid found: {event_data.get("sessionid")}')
        def print_visitorid_generated():
            print(f'DEBUG: sentry: visitorid not found, generated new: {event_data.get("visitorid")}')
        def print_visitorid_found():
            print(f'DEBUG: sentry: visitorid found: {event_data.get("visitorid")}')
        def print_userid_generated():
            print(f'DEBUG: sentry: userid not found, generated new: {event_data.get("userid")}')
        def print_userid_found():
            print(f'DEBUG: sentry: userid found: {event_data.get("userid")}')
        def print_userid_blank():
            print(f'DEBUG: sentry: no userid')
        def print_timings_data():
            metric,counter_name,counter_cutoff,record_count,counter_limit,assessment = event_data
            print(f'DEBUG: sentry: checking for speeders: metric == {metric}, checking {counter_name} interval ({counter_cutoff}), found {record_count} attempts with limit of {counter_limit}; assessment: {"PASS" if assessment else "REJECT"}')
        handlers = {
            'headers/cookies/sessionid': print_headers_cookies_sessionid,
            'sessionid generated': print_sessionid_generated,
            'sessionid found': print_sessionid_found,
            'visitorid generated': print_visitorid_generated,
            'visitorid found': print_visitorid_found,
            'userid generated': print_userid_generated,
            'userid found': print_userid_found,
            'userid blank': print_userid_blank,
            'timings metric': print_timings_data,
        }
        handler = handlers.get(metric,None)
        if not handler:
            raise Exception(f'Sentry: debug_log(): unrecognized metric: {metric}')
        try:
            return handler()
        except Exception as e:
            print(f'Sentry: debug_log(): error: {e}',file=sys.stderr)
            print(f'Sentry: debug_log(): error: {e}',file=sys.stdout)

    def assign_ipinfo(self):
        return {}

    def assign_cookieinvestigationinfo(self):
        return {}

    def assign_deviceinfo(self):
        return {}

    def assign_langprefinfo(self):
        return {}

    def assign_tzinfo(self):
        # TODO:
        return {}

    def assign_sessionid(self):
        response = {}
        sessionid = self.request.cookies.get("sessionid")
        if sessionid:
            sessionid = sessionid.value

        if not sessionid or sessionid not in self.context.session_storage:
            sessionid = secrets.token_urlsafe(32)
            self.context.session_storage[sessionid] = {}
            response['sessionid'] = sessionid
            self.debug_log(metric='sessionid generated',event_data=response)
        else:
            response['sessionid'] = sessionid
            self.debug_log(metric='sessionid found',event_data=response)
        session_data = self.context.session_storage[sessionid]
        response['session_data'] = session_data
        return response

    def assign_visitorid(self):
        response = {}
        visitorid = self.response.get("session_data").get('visitorid',None)

        if not visitorid:
            visitorid = secrets.token_urlsafe(32)
            self.context.visitor_storage[visitorid] = {}
            response['visitorid'] = visitorid
            self.debug_log(metric='visitorid found',event_data=response)
        else:
            response['visitorid'] = visitorid
            if visitorid not in self.context.visitor_storage:
                raise SentryReject('visitorid not found')
            self.debug_log(metric='visitorid found',event_data=response)
        visitors_data = self.context.visitor_storage[visitorid]
        response['visitors_data'] = visitors_data
        return response

    def assign_userid(self):
        response = {}
        userid = self.response.get("visitors_data").get('visitorid',None)

        if not userid:
            userid = None
            response['userid'] = userid
            self.debug_log(metric='userid blank',event_data=response)
        else:
            if userid not in self.user_storage:
                raise SentryReject('userid not found')
            response['userid'] = userid
            self.debug_log(metric='userid found',event_data=response)
        user_data = self.user_storage[userid] if userid else None
        response['user_data'] = user_data
        return response

    def assign_ratelimitinfo(self):
        context = self.context
        request = self.request
        time_now = request.time_now
        time_now_str = f'{time_now.isoformat()}'
        with context.redis.pipeline() as redis_pipe_read, context.redis.pipeline() as redis_pipe_write:
            try:
                if request.ip:
                    redis_pipe_write.rpush(f"auth:timing_counter:ip:{request.ip}", time_now_str)
                    redis_pipe_write.expire(f"auth:timing_counter:ip:{request.ip}", MAX_TIMINGCOUNTER_AGE_PULL)
                if self.response.get("sessionid"):
                    redis_pipe_write.rpush(f"auth:timing_counter:sessionid:{self.response.get("sessionid")}", time_now_str)
                    redis_pipe_write.expire(f"auth:timing_counter:sessionid:{self.response.get("sessionid")}", MAX_TIMINGCOUNTER_AGE_PULL)
                if self.response.get("sessionid") and request.ip:
                    last_sessions_from_ip = context.redis.lrange(f"auth:session2ip:ip:{request.ip}", -MAX_TIMINGCOUNTER_RECORDS_PULL-1, -1)
                    did_session_from_this_ip_exist_before = len([record for record in last_sessions_from_ip if record==self.response.get("sessionid")])>0
                    if not did_session_from_this_ip_exist_before:
                        redis_pipe_write.rpush(f"auth:timing_counter:newsessionsperip:{request.ip}", time_now_str)
                        redis_pipe_write.expire(f"auth:timing_counter:newsessionsperip:{request.ip}", MAX_TIMINGCOUNTER_AGE_PULL)
                    redis_pipe_write.rpush(f"auth:session2ip:ip:{request.ip}", f'{self.response.get("sessionid")}')
                    redis_pipe_write.expire(f"auth:session2ip:ip:{request.ip}", MAX_TIMINGCOUNTER_AGE_SESSIONPERIP_PULL)
                if self.response.get("visitorid"):
                    redis_pipe_write.rpush(f"auth:timing_counter:visitorid:{self.response.get("visitorid")}", time_now_str)
                    redis_pipe_write.expire(f"auth:timing_counter:visitorid:{self.response.get("visitorid")}", MAX_TIMINGCOUNTER_AGE_PULL)
                if self.response.get("userid"):
                    redis_pipe_write.rpush(f"auth:timing_counter:userid:{self.response.get("userid")}", time_now_str)
                    redis_pipe_write.expire(f"auth:timing_counter:userid:{self.response.get("userid")}", MAX_TIMINGCOUNTER_AGE_PULL)
                redis_pipe_write.execute()
                redis_pipe_write.reset()

                timings_entries = []
                if request.ip:
                    redis_pipe_read.lrange(f"auth:timing_counter:ip:{request.ip}", -MAX_TIMINGCOUNTER_RECORDS_PULL-1, -1)
                    timings_entries.append('ip')
                if self.response.get("sessionid"):
                    redis_pipe_read.lrange(f"auth:timing_counter:sessionid:{self.response.get("sessionid")}", -MAX_TIMINGCOUNTER_RECORDS_PULL-1, -1)
                    timings_entries.append('sessionid')
                if self.response.get("sessionid") and request.ip:
                    redis_pipe_read.lrange(f"auth:timing_counter:newsessionsperip:{self.response.get("sessionid")}", -MAX_TIMINGCOUNTER_RECORDS_PULL-1, -1)
                    timings_entries.append('newsessionsperip')
                if self.response.get("visitorid"):
                    redis_pipe_read.lrange(f"auth:timing_counter:visitorid:{self.response.get("visitorid")}", -MAX_TIMINGCOUNTER_RECORDS_PULL-1, -1)
                    timings_entries.append('visitorid')
                if self.response.get("userid"):
                    redis_pipe_read.lrange(f"auth:timing_counter:userid:{self.response.get("userid")}", -MAX_TIMINGCOUNTER_RECORDS_PULL-1, -1)
                    timings_entries.append('userid')
                timings_age_log = redis_pipe_read.execute()
                redis_pipe_read.reset()
                timings_age_log = { metric: [time_now-datetime.fromisoformat(dt) for dt in log] for (metric,log) in zip(timings_entries,timings_age_log) }
                for metric, age_log in timings_age_log.items():
                    for counter_name, counter_cutoff, counter_data in TIMINGS_INTERVALS:
                        counter_cutoff = timedelta(seconds=counter_cutoff)
                        if metric in counter_data:
                            counter_limit = counter_data[metric]
                            record_count = len([age for age in age_log if age<counter_cutoff ])
                            self.debug_log(metric='timings metric',event_data=(metric,counter_name,counter_cutoff,record_count,counter_limit,not(record_count>counter_limit),))
                            if record_count>counter_limit:
                                raise SentryReject(f'User is acting too fast: {record_count} attempts within {counter_cutoff} ({counter_name}) for {metric}, limit is {counter_limit}')
            except (redis.exceptions.ConnectionError, ConnectionRefusedError) as e:
                raise ConnectionRefusedError(f'Failed to connect to redis: {e}') from e
        return {}

    def assign_riskscoringinfo(self):
        # TODO:
        return {}


class Sentry:
    def __init__(self):
        self.session_storage = dict() # SessionStorage()
        self.visitor_storage = dict() # VisitorStorage()
        self.user_storage = UserStorage()

    def process(
        self,
        context: ContextForSentry,
        request: RequestToSentry,
    ):
        return SentryRecord(
            ContextForSentryProcess(
                session_storage = self.session_storage,
                visitor_storage = self.visitor_storage,
                user_storage = self.user_storage,
                redis=context.redis,
            ),
            request,
        )
