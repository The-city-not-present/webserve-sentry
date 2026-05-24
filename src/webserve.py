
import argparse
import traceback, sys
from dotenv import load_dotenv
import os
from datetime import datetime, UTC
# src/webserve.py
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from http.cookies import SimpleCookie
import redis
import json



if __name__ == '__main__':
    # run as a program
    from sentry import Sentry, SentryReject, RequestToSentry, ContextForSentry
elif '.' in __name__:
    # package
    from .sentry import Sentry, SentryReject, RequestToSentry, ContextForSentry
else:
    # included with no parent package
    from sentry import Sentry, SentryReject, RequestToSentry, ContextForSentry






# STDOUT_COLOR_RED = "\033[91m"
STDOUT_COLOR_RED = "\033[31m"
STDOUT_COLOR_RESET = "\033[0m"
STDOUT_COLOR_GREEN = "\033[32m"







load_dotenv()
PORT_NUM = os.getenv("PORT_NUM", "")
REDIS_ACCESS_HOST = os.getenv("REDIS_ACCESS_HOST", "")



def get_handler():
    redis_host = (None,None,)
    try:
        redis_host = f'{redis_host}'.split(':')
        assert len(redis_host) == 2, f'Must be host:port: {REDIS_ACCESS_HOST}'
        redis_host = (f'{redis_host[0]}'.strip(),int(redis_host[1]))
    except Exception as e:
        raise Exception(f'Can\'t parse redis port spec: {REDIS_ACCESS_HOST}') from e
    r = redis.Redis(host=redis_host[0], port=redis_host[1], decode_responses=True)
    sentry = Sentry()
    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            try:

                time_now = datetime.now(UTC)
                ip = self.headers.get("X-Real-IP")
                request_path = urlparse(self.path).path
                headers = self.headers # case-insensitive dict
                cookie_header = self.headers.get('Cookie')
                cookies = SimpleCookie(cookie_header)

                result = {}
                try:
                    print(f"Incoming auth check from {ip}, requested {request_path}, on {time_now}...") # , end="", flush=True
                    # print(self.headers)

                    result = sentry.process(
                        ContextForSentry(
                            redis=r,
                        ),
                        RequestToSentry(
                            ip = ip,
                            request_path = request_path,
                            headers = headers,
                            cookies = cookies,
                            time_now = time_now,
                        )
                    ).response

                    assert 'visitorid' in result
                    assert 'sessionid' in result
                    send_cookie = SimpleCookie()
                    send_cookie["sessionid"] = result['sessionid']
                    send_cookie["sessionid"]["httponly"] = True
                    send_cookie["sessionid"]["secure"] = True
                    send_cookie["sessionid"]["path"] = "/"
                    send_cookie["visitorid"] = result['visitorid']
                    send_cookie["visitorid"]["httponly"] = True
                    send_cookie["visitorid"]["secure"] = True
                    send_cookie["visitorid"]["path"] = "/"

                    content_type = 'text/html' if not (self.headers.get("Accept") == "application/json") else 'application/json'
                    self.send_response(200)
                    self.send_header(f"Content-type", f"{content_type}; charset=utf-8")
                    for morsel in send_cookie.values():
                        # TODO: make sure nginx forwards / merged cookies
                        self.send_header("Set-cookie", morsel.OutputString())
                        print(f'(trying to) set-cookie (from sentry service): {morsel.OutputString()}')
                    self.end_headers()
                    print("Incoming auth check ->  ok!")
                    try:
                        redis_pipe_log = r.pipeline()
                        redis_pipe_log.rpush("auth:requests", json.dumps({
                            'datetime': f'{time_now.isoformat()}',
                            'ip': ip,
                            'request_path': request_path,
                            'result': 'allowed',
                            'details': {
                                'sessionid': result.get('sessionid',None),
                                'visitorid': result.get('visitorid',None),
                                'userid': result.get('userid',None),
                            },
                        }))
                        redis_pipe_log.execute()
                    except (redis.exceptions.ConnectionError, ConnectionRefusedError) as e:
                        raise ConnectionRefusedError(f'Failed to connect to redis: {e}') from e

                except SentryReject as e:

                    content_type = 'text/html' if not (self.headers.get("Accept") == "application/json") else 'application/json'
                    self.send_response(401)
                    self.send_header(f"Content-type", f"{content_type}; charset=utf-8")
                    self.end_headers()
                    print(f"Incoming auth check ->  rejected! Reason: {e}")
                    try:
                        redis_pipe_log = r.pipeline()
                        redis_pipe_log.rpush("auth:requests", json.dumps({
                            'datetime': f'{time_now.isoformat()}',
                            'ip': ip,
                            'request_path': request_path,
                            'result': 'reject',
                            'details': f'{e}',
                        }))
                        redis_pipe_log.execute()
                    except (redis.exceptions.ConnectionError, ConnectionRefusedError) as e:
                        raise ConnectionRefusedError(f'Failed to connect to redis: {e}') from e
                    return;

            except Exception as e:
                self.send_response(500)
                self.end_headers()
                print('',file=sys.stderr)
                print('Stack trace:',file=sys.stderr)
                print('',file=sys.stderr)
                traceback.print_exception(e,limit=20)
                print('',file=sys.stderr)
                print('',file=sys.stderr)
                print('',file=sys.stderr)
                print('Error:',file=sys.stderr)
                print('',file=sys.stderr)
                print(f'{STDOUT_COLOR_RED}{e}{STDOUT_COLOR_RESET}',file=sys.stderr)
                print('',file=sys.stderr)

        def do_GET(self):
            self.handle_request()

        def do_HEAD(self):
            self.handle_request()

    return Handler


def run(address='0.0.0.0',port_num=PORT_NUM):
    try:
        port_num = int(port_num)
    except Exception as e:
        raise Exception(f'Can\'t parse port_num param: {port_num}') from e
    server = HTTPServer((address, port_num), get_handler())
    print('Calling serve_forever()!')
    server.serve_forever()





def entry_point(*argcs,**kwargs):
    try:
        time_start = datetime.now()
        script_name = 'webserve'

        parser = argparse.ArgumentParser(
            description="Webserve",
            prog='webserve --program webserve'
        )
        parser.add_argument(
            '--port',
            help='port number',
            type=int,
            required=False
        )
        # args = None
        # args_rest = None
        # if( ('arglist_strict' in config) and (not config['arglist_strict']) ):
        #     args, args_rest = parser.parse_known_args()
        # else:
        args = None
        try:
            args = parser.parse_args(*argcs,**kwargs)
        except SystemExit as e:
            print(f'{STDOUT_COLOR_RED}Error: Invalid command-line arguments{STDOUT_COLOR_RESET}',file=sys.stderr)
            raise e

        port_num = PORT_NUM
        if args.port:
            port_num = args.port
            try:
                port_num = int(port_num)
            except Exception as e:
                raise Exception(f'Can\'t parse port_num param: {port_num}') from e

        result = run(
            address='0.0.0.0',
            port_num = port_num,
        )

        time_finish = datetime.now()
        print('{script_name}: finished at {dt} (elapsed {duration})'.format(dt=time_finish,duration=time_finish-time_start,script_name=script_name))
    except Exception as e:
        # the program is designed to be user-friendly
        # that's why we reformat error messages a little bit
        # stack trace is still printed (I even made it longer to 20 steps!)
        # but the error message itself is separated and printed as the last message again

        # for example, I don't write "print('File Not Found!');exit(1);", I just write "raise FileNotFoundErro()"
        print('',file=sys.stderr)
        print('Stack trace:',file=sys.stderr)
        print('',file=sys.stderr)
        traceback.print_exception(e,limit=20)
        print('',file=sys.stderr)
        print('',file=sys.stderr)
        print('',file=sys.stderr)
        print('Error:',file=sys.stderr)
        print('',file=sys.stderr)
        print(f'{STDOUT_COLOR_RED}{e}{STDOUT_COLOR_RESET}',file=sys.stderr)
        print('',file=sys.stderr)
        exit(1)

if __name__ == '__main__':
    entry_point()
