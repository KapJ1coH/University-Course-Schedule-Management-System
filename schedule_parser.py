from datetime import datetime
import json
import re
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU

from bs4 import BeautifulSoup

LOCATION = {
    "Hall Building": "1455 de Maisonneuve Boulevard West",
    "H": "1455 de Maisonneuve Boulevard West",
    "Learning square": "1535 de Maisonneuve Boulevard West",
    "LS": "1535 de Maisonneuve Boulevard West",
    "John Molson Building": "1450 Guy Street",
    "MB": "1450 Guy Street",
    "EV Building": "1515 Sainte-Catherine Street West",
    "Faubourg Building": "1250 Guy Street",
    "FB": "1250 Guy Street",
    "Grey Nuns Building": "1190 Guy Street",
    "Guy-Metro Building": "1616 Sainte-Catherine Street West",
    "J.W. McConnell Building": "1400 De Maisonneuve Boulevard West",
    "LB Building": "1400 De Maisonneuve Boulevard West",
    "MB Building": "1450 Guy Street",
    "SP Building": "2149 Mackay Street",
    "VA Building": "1395 René-Lévesque Boulevard West",
    "Webster Library": "1400 De Maisonneuve Boulevard West",

}

"""
New format:
 - Grab all the course info from the course cart
 - Grab university closed dates from the academic calendar

 - Make the program event based
    - For each course, create a list of events
    - Each event should have a start date, end date, start time, end time, location, instructor and days of the week
    - Each event should have a recurrence rule
    - Allow for multiple days per block
    - Represent days in this format: 'MO,TU,WE,TH,FR'
    - Add a recurrence rule for each

- Course, Event are both objects
- Course has a list of events and general course info
- Course contains start and end date, course instructor, course title, course subtitle, course number, course section, course session, course credits
- Event contains start and end time, location, days of the week, recurrence rule
    - Location should be a tuple of (building, room)
    - Building should be a string with the full address
    - No location --> Empty string

- Enable event deletion and modification
    - Delete all events for a course
    - Delete all events for a course on a specific day
    - Modify based on data stored in a file.

"""

"""
This module is responsible for parsing the schedule from the course cart.

"""


class ClassEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (TimeBlock, Course)):
            return obj.__dict__
        return super().default(obj)

class TimeBlock:
    """
    Represents a single event in a course.
    """

    def __init__(self, start_date, end_date, start_time, end_time, days, building, room, instructor, class_number,
                 section, component):
        """
        :param component:
        :type start_date: datetime        :type end_date:
        :param start_date: Class start date
        :param end_date: Class end date
        :param start_time: Class start time
        :param end_time: Class end time
        :param days: Days of the week the class is on
        :param building: Building the class is in
        :param room: Room the class is in
        :param instructor: Instructor of the class
        :param class_number: Class number
        :param section: Class section
        :param component: What class it is. Ex: LEC
        """
        self.start_date = start_date
        self.end_date = end_date
        self.start_time = start_time
        self.end_time = end_time
        self.days = days
        self.building = building
        self.room = room
        self.instructor = instructor
        self.class_number = class_number
        self.section = section
        self.component = component

    def next_weekday(self, start_date, day):
        match day:
            case "Mo":
                return start_date + relativedelta(weekday=MO(1))
            case "Tu":
                return start_date + relativedelta(weekday=TU(1))
            case "We":
                return start_date + relativedelta(weekday=WE(1))
            case "Th":
                return start_date + relativedelta(weekday=TH(1))
            case "Fr":
                return start_date + relativedelta(weekday=FR(1))
            case "Sa":
                return start_date + relativedelta(weekday=SA(1))
            case "Su":
                return start_date + relativedelta(weekday=SU(1))
            case _:
                return start_date

    # to string method
    def __str__(self):
        return f"Start date: {self.start_date}\n" \
               f"End date: {self.end_date}\n" \
               f"Start time: {self.start_time}\n" \
               f"End time: {self.end_time}\n" \
               f"Days: {self.days}\n" \
               f"Building: {self.building}\n" \
               f"Room: {self.room}\n" \
               f"Instructor: {self.instructor}\n" \
               f"Class number: {self.class_number}\n" \
               f"Section: {self.section}\n"

    def empty_object_for_json(self):
        self.start_date = None
        self.end_date = None
        self.start_time = None
        self.end_time = None
        self.days = None
        self.building = None
        self.room = None
        self.instructor = None
        self.class_number = None
        # self.section = None
        # self.component = None


class Course:
    """
    This class represents a single course.
    """

    def __init__(self, course_title, course_subtitle, course_credits,
                 events):
        self.course_title = course_title
        self.course_subtitle = course_subtitle
        self.course_credits = course_credits
        self.events = events



class BreakLoopException(Exception):
    pass


def parse_course_cart(with_modifications=False):
    """
    Goes through the html table, and parses the course cart.
    Each block is one course with all the information.
    :return: List of courses
    """
    courses = {}
    table = extract_table('summer_schedule_list_view.html').find('tbody')

    units_regex = re.compile(r'DERIVED_REGFRM1_UNT_TAKEN$\d+')

    count = 0


    for i, block in enumerate(table.findChildren('tr', recursive=False)):
        count, course = go_thru_each_class(block, count, i)
        courses[course.course_title] = course

    if with_modifications:
        # open a file with the modifications

        # generate a dict to paste later
        courses_temp = courses.copy()

        # go through the dict
        for key in courses_temp:
            for event in courses_temp[key].events:
                event.empty_object_for_json()

        with open('modifications.json', 'w') as f:
            f.write(json.dumps(courses_temp, indent=4, cls=ClassEncoder))

        # TODO: check that json was modified. Maybe use a hashing thingy.
        #  If modified, replace the values in Courses with data from JSON



def go_thru_each_class(block, count, i):
    """
    Goes through each class in the table of usually 5 classes.
    It will be later merged into a dictionary with a key of the class name and a value of the class object.
    :param block: Soup object of the class block
    :param count: count used in the next method
    :param i: Used to find unique ids of classes
    :return:
    """
    class_name = block.find('h3', class_="ui-bar").text
    class_name, class_subtitle = class_name.split(' - ')
    units = block.find('span', id=f'DERIVED_REGFRM1_UNT_TAKEN${i}').text
    time_blocks = []
    for row in block.find('table', id=f"CLASS_MTG_VW$scroll${i}").find('table', class_='ui-table').find(
            'tbody').findAll('tr'):
        """
        Example data extracted:
        3103 CCCG Tutorial MoWe 6:30PM - 8:10PM H 521 SGW JOUMANA DARGHAM 
        03/07/2023 - 10/08/2023
        """
        try:
            count, time_block = go_thru_each_timeblock(count, row)
        except BreakLoopException:
            continue
        time_blocks.append(time_block)
    course = Course(class_name, class_subtitle, units, time_blocks)

    return count, course


def go_thru_each_timeblock(count, row):
    """
    Goes through each time block in a course.

    :param count: Count of the ui element since each element has a unique id, an int is appended to the end of the id
    :param row: One specific class/time block
    :return: Count: Updated count, time_block: TimeBlock object
    """
    cls_number = ""
    if not (cls_number := row.find('span', id=f"DERIVED_CLS_DTL_CLASS_NBR${count}")):
        print("No class number found")
        raise BreakLoopException

    cls_number = cls_number.text
    cls_section = row.find('a', id=f"MTG_SECTION${count}").text

    # :3 to shorten from Lecture to Lec
    cls_component = row.find('span', id=f"MTG_COMP${count}").text[:3]

    cls_day_time = row.find('span', id=f"MTG_SCHED${count}").text
    days, start_time, end_time = clean_cls_day_time(cls_day_time)

    cls_room = row.find('span', id=f"MTG_LOC${count}").text
    building, room = clean_cls_room(cls_room)
    cls_instructor = row.find('span', id=f"DERIVED_CLS_DTL_SSR_INSTR_LONG${count}").text

    cls_dates = row.find('span', id=f"MTG_DATES${count}").text
    start_date, end_date = clean_cls_dates(cls_dates)

    cls = TimeBlock(
        class_number=cls_number,
        section=cls_section,
        days=days,
        start_time=start_time,
        end_time=end_time,
        building=building,
        room=room,
        instructor=cls_instructor,
        start_date=start_date,
        end_date=end_date,
        component=cls_component
    )
    count += 1
    return count, cls


def clean_cls_day_time(cls_day_time):
    """
    Transform a string of location/time into a tuple of days and times.
    :param cls_day_time: String. Ex: MoWe 6:30PM - 8:10PM
    :return: String, String, datetime.time, datetime.time. Ex: MO,WE,18:30,20:10
    """
    days, time = cls_day_time.split(' ', 1)
    # Split days string into groups of 2 strings. Ex: MoWe -> [MO, WE]
    days = [days[i:i + 2].upper() for i in range(0, len(days), 2)]
    start_time, end_time = time.split(' - ')
    start_time = datetime.strptime(start_time, '%I:%M%p').time()
    end_time = datetime.strptime(end_time, '%I:%M%p').time()
    return days, start_time, end_time


def clean_cls_dates(cls_dates):
    """
    Transform a string of dates into a tuple of start and end dates.
    :param cls_dates: String. Ex: 03/07/2023 - 10/08/2023
    :return: datetime.date, datetime.date. Ex: 2023-03-07, 2023-10-08
    """
    start_date, end_date = cls_dates.split(' - ')
    start_date = datetime.strptime(start_date, '%d/%m/%Y').date()
    end_date = datetime.strptime(end_date, '%d/%m/%Y').date()
    return start_date, end_date


def clean_cls_room(cls_room):
    """
    Transform a string of location into a tuple of building and room.

    - If room is not specified, it will be N/A.
    - If building abbreviation is in the global LOCATION dictionary,
    it will be replaced with the full address and room will include
    the building abbreviation at the start. Ex: H 521 SGW -> H521
    :param cls_room: String. Ex: H 521 SGW
    :return:
    """
    try:
        building, room = cls_room.split(' ')[:2]
    except ValueError:
        building = cls_room
        room = "N/A"

    building = building.upper()
    if building in LOCATION:
        room = building + room
        building = LOCATION[building]

    return building, room


def extract_table(filename):
    html = read_html(filename)
    soup = BeautifulSoup(html, 'html.parser')
    return soup.find('table', id='ACE_STDNT_ENRL_SSV2$0')


def read_html(name):
    with open(name, 'r') as f:
        return f.read()


if __name__ == '__main__':
    parse_course_cart(True)
