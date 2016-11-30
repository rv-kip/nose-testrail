"""Plugin to send test results to TestRail and/or record tests->testrail_id mappings"""
import base64
from datetime import datetime
import io
import json
import os
import traceback
import urllib2

from nose.plugins import Plugin

CASE_ID = 'case_id'


def case_id(id=None):
    def wrap_ob(ob):
        setattr(ob, CASE_ID, id)
        return ob
    return wrap_ob


def testrail_case_id(id=None):
    def wrap_ob(ob):
        setattr(ob, CASE_ID, id)
        return ob
    return wrap_ob


class NoseTestRail(Plugin):
    name = 'nose-testrail'

    def options(self, parser, env=os.environ):
        super(NoseTestRail, self).options(parser, env=env)

    def configure(self, options, conf):
        super(NoseTestRail, self).configure(options, conf)
        if not self.enabled:
            return
        else:
            self.testrail = {}
            self.testrail['host'] = os.environ.get('TESTRAIL_HOST', None)
            self.testrail['user'] = os.environ.get('TESTRAIL_USERNAME', None)
            self.testrail['password'] = os.environ.get('TESTRAIL_PASSWORD', None)
            self.testrail['run_id'] = os.environ.get('TESTRAIL_RUN_ID', None)
            self.testrail['mapping_file'] = os.environ.get('TESTRAIL_MAPPING_FILE', 'testrail_mapping.csv')
            self.testrail['mapping_only'] = os.environ.get('TESTRAIL_MAPPING_ONLY', None)

    def begin(self):
        self.time_before = datetime.now()

    def startTest(self, test):
        self.test_case_id = self.get_test_case_id(test)
        self.result = {}

    def stopTest(self, test):
        if self.test_case_id:
            test_class = test.id().split('.')[-2]
            test_name = test.id().split('.')[-1]
            if self.testrail['mapping_file'] and test_class and test_name:
                with io.open(self.testrail['mapping_file'], 'ab') as f:
                    f.write('%s:%s,%d' % (test_class, test_name, self.test_case_id) + "\n")

            # Check for TestRail API Requirements before going further
            if (
                self.testrail['host'] and
                self.testrail['user'] and
                self.testrail['password'] and
                self.testrail['run_id'] and
                not self.testrail['mapping_only']
            ):
                time_after = datetime.now()
                delta = time_after - self.time_before
                self.result['elapsed'] = self.elapsed_time(delta.seconds)
                self.time_before = time_after
                self.send_result(self.result)

    def addSuccess(self, test):
        self.result['status_id'] = 1
        self.result['comment'] = 'test PASS'

    def addFailure(self, test, err):
        self.result['status_id'] = 5
        self.result['comment'] = self.formatErr(err)

    def addError(self, test, err):
        self.result['status_id'] = 5
        self.result['comment'] = self.formatErr(err)

    def send_result(self, result):
            uri = 'https://{0}/index.php?/api/v2/add_result_for_case/{1}/{2}'.format(
                self.testrail['host'],
                self.testrail['run_id'],
                self.test_case_id
            )
            self.__send_request('POST', uri, result)

    def __send_request(self, method, uri, data):
        request = urllib2.Request(uri)
        if (method == 'POST'):
            request.add_data(json.dumps(data))
        auth = base64.b64encode('%s:%s' % (
            self.testrail['user'],
            self.testrail['password'],
        ))
        request.add_header('Authorization', 'Basic %s' % auth)
        request.add_header('Content-Type', 'application/json')

        try:
            response = urllib2.urlopen(request).read()
        except urllib2.HTTPError as e:
            response = e.read()

        if response:
            result = json.loads(response)
        else:
            result = {}

        if e is not None:
            if result and 'error' in result:
                error = '"' + result['error'] + '"'
            else:
                error = 'No additional error message received'
            raise APIError('TestRail API returned HTTP %s (%s)' % (e.code, error))

        return result

    def formatErr(self, err):
        """format error"""
        exctype, value, tb = err
        tr = traceback.format_exception(exctype, value, tb)
        return '' . join(tr)

    def get_test_case_id(self, test):
        test_name = test.id().split('.')[-1]
        test_method = getattr(test.test, test_name, None)
        test_case_id = getattr(test_method, CASE_ID, None)
        return test_case_id

    # TODO: Also check accuracy
    def elapsed_time(seconds, separator=' '):
        suffixes = ['y', 'w', 'd', 'h', 'm', 's']
        time = []
        parts = [
            (suffixes[0], 60 * 60 * 24 * 7 * 52),
            (suffixes[1], 60 * 60 * 24 * 7),
            (suffixes[2], 60 * 60 * 24),
            (suffixes[3], 60 * 60),
            (suffixes[4], 60),
            (suffixes[5], 1)
        ]
        for suffix, length in parts:
            value = seconds / length
            if value > 0:
                seconds = seconds % length
                time.append('%s%s' % (str(value), suffix))
            if seconds < 1:
                break
        return ' ' . join(time)


class APIError(Exception):
    pass
