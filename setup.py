try:
    from setuptools import setup
except ImportError:
    print "setuptools not found: using distutils"
    from distutils.core import setup

reqs = ["gevent", "flask", "gevent_socketio", "pyte"]
setup(
    name = "Webterm",
    version = "pretty old",
    description = "web-based terminal",
    author = "Jeremiah \"Zekka\" Nelson",
    author_email = "zekka@messageintercepted.com",
    url = "http://github.com/Zekka/webterm",
    # apparently setuptools is bugging out and just delegating in a way that
    # fails to pass this on, so we provide it both with the antiquated and
    # the correct name
    install_requires = reqs,
    requires = reqs,
    packages = ["webterm"]
)
