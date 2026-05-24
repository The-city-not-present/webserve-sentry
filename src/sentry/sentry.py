
# import uuid
import secrets

from .session_storage import SessionStorage
from .visitors_storage import VisitorsStorage
from .users_storage import UsersStorage


class SentryReject(Exception):
    """Acts as HTTP 401"""


class Sentry:
    def __init__(self):
        self.session_storage = dict() # SessionStorage()
        self.visitors_storage = dict() # VisitorsStorage()
        self.users_storage = UsersStorage()

    def process(self,ip,path,headers,cookies):
        """
        Session id should not break/invalidate on ip changes
        It must break/invalidate on device/ua change
        TODO:
        - grab ip
        - - possibly ip type
        - - possibly geo mismatch
        - possibly other cookies
        - user-agent
        - - mobile-non-mobile
        - - so, implement device fingerprinting
        - Accept, Accept-Language, Accept-Encoding
        - TZ info
        - request timing!!!
        - imlement "risk-scoring"
        - defensive anti-bot protections (hidden fields, and similar
        - get more info on Content-Security-Policy (CSP) → prevents XSS, Strict-Transport-Security (HSTS) → forces HTTPS, X-Frame-Options → prevents clickjacking, X-Content-Type-Options → prevents MIME sniffing)
        - set JWT
        """
        response = {}

        # is existing session?
        session_id = cookies.get("sessionid")
        if session_id:
            session_id = session_id.value

        # if not not session_id:
        #     print(f'DEBUG: received session_id in cookies: {session_id}')
        if not session_id:
            session_id = secrets.token_urlsafe(32)
            # print(f'DEBUG: no session id, generating: {session_id}')
            self.session_storage[session_id] = {}
        else:
            if session_id not in self.session_storage:
                raise SentryReject('session_id not found')
        session_data = self.session_storage[session_id]

        # is existing visitor?
        visitor_id = session_data.get('visitor_id',None)

        if not visitor_id:
            visitor_id = secrets.token_urlsafe(32)
            self.visitors_storage[visitor_id] = {}
        else:
            if visitor_id not in self.visitors_storage:
                raise SentryReject('visitor_id not found')
        visitors_data = self.visitors_storage[visitor_id]

        # is existing user?
        user_id = visitors_data.get('visitor_id',None)

        if not user_id:
            user_id = None
        else:
            if user_id not in self.users_storage:
                raise SentryReject('user_id not found')
        user_data = self.users_storage[user_id] if user_id else None

        response['sessionid'] = session_id
        response['visitorid'] = visitor_id
        return response
