import py, pytest
import time, os

class BaseTest(object):

    # nondestructive unless marked otherwise
    pytestmark = pytestmark = [pytest.mark.nondestructive]

    def failing_method(self):
        raise Exception("OMG! failing method!")

    def pass_the_third_time(self, testname):
        filename = testname + ".res"
        state = None
        try:
            fileh = open(filename, 'r')
            state = fileh.read()
            fileh.close()
        except IOError:
            state = ''

        if state == '':
            fileh = open(filename, 'w')
            fileh.write('fail')
            fileh.flush()
            raise Exception("Failing the first time")
        elif state == 'fail':
            fileh = open(filename, 'w')
            fileh.write('pass')
            fileh.flush()
            raise Exception("Failing the second time")
        elif state == 'pass':
            os.popen('rm -f %s' % filename)  # delete the file
            return  # pass the method
        else:
            raise Exception("unexpected data in file %s: %s" % (filename, state))
