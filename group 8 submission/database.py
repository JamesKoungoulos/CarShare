#!/usr/bin/env python3

from modules import pg8000
import configparser


# Define some useful variables
ERROR_CODE = 55929

# Dictionary for simple front-end error codes
# 01 - Login query failed
# 02 - Homebay transaction failed
# 03 - New booking transaction failed
# 04 - Get all bookings failed
# 05 - Get booking details failed
# 06 - Getting car details failed
# 07 - Getting all cars failed
# 08 - Getting all bays failed
# 09 - Getting bay details failed
# 10 - Searching bays failed
# 11 - Getting cars in bay failed

#####################################################
##  Database Connect
#####################################################

def database_connect():
    # Read the config file
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Create a connection to the database
    connection = None
    try:
        connection = pg8000.connect(database=config['DATABASE']['user'],
            user=config['DATABASE']['user'],
            password=config['DATABASE']['password'],
            host=config['DATABASE']['host'])
    except pg8000.OperationalError as e:
        print("""Error, you haven't updated your config.ini or you have a bad
        connection, please try again. (Update your files first, then check
        internet connection)
        """)
        print(e)
    #return the connection to use
    return connection

#####################################################
##  Login
#####################################################

def check_login(user, password):

    val = {}

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_member = """SELECT A.nickname, A.nametitle, A.namegiven, A.namefamily, A.address, B.name, A.since, A.subscribed, A.stat_nrofbookings, A.email
                        FROM Member A LEFT OUTER JOIN CarBay B ON (A.homebay = B.bayid)
                        WHERE (A.email = %s OR A.nickname = %s) AND A.password =%s"""

        cursor.execute(sql_member, (user, user, password,))
        val = cursor.fetchone() 

        cursor.close()
        connection.close()

    except: 
        print("ERROR CODE 01")
        cursor.close()
        connection.close()

    return val


#####################################################
##  Homebay
#####################################################
def update_homebay(email, bayname):
    
    try:

        connection = database_connect()
        cursor = connection.cursor()

        ## get the id of the bay
        sql_homebay = """SELECT bayid 
                         FROM Carbay
                         WHERE name = %s"""

        # set the user's bay to this bay id
        sql_member = """UPDATE Member
                        SET homebay = %s
                        WHERE email = %s"""

        cursor.execute(sql_homebay, (bayname,))

        bay = str(cursor.fetchone())[1:-1] # remove brackets 

        cursor.execute(sql_member, (bay, email))

        connection.commit()
        cursor.close()
        connection.close()

        return True
    except:
        print("ERROR CODE 02")
        connection.rollback()
        cursor.close()
        connection.close()

        return False


#####################################################
##  Booking (make, get all, get details)
#####################################################

def make_booking(email, car_rego, date, hour, duration):

    try:

        connection = database_connect()
        cursor = connection.cursor()

        cursor.execute("""SET TRANSACTION ISOLATION LEVEL SERIALIZABLE""")

        # retrieve the user's id number for use later

        sql_id      = """SELECT memberno 
                         FROM Member
                         WHERE email = %s"""

        cursor.execute(sql_id, (email,))

        memid = int(str(cursor.fetchone())[1:-1])

        # generate date and time objects, calculate start and end timestamps, and format back into strings for bound parameterisation

        fdate = pg8000.Date(int(date[0:4]), int(date[5:7]), int(date[8:10]))
        fhour = pg8000.Time(int(hour),0,0)
        fduration = pg8000.Time(int(duration),0,0)

        sql_starttime = """SELECT (%s + %s::interval)::text"""
        cursor.execute(sql_starttime, (fdate,fhour,))
        start = str(cursor.fetchone())[1:-1]

        sql_endtime = """SELECT ((%s + %s::interval) + %s::interval)::text"""
        cursor.execute(sql_endtime, (fdate, fhour, fduration,))
        end = str(cursor.fetchone())[1:-1]

        # check that the time selected is reasonable

        sql_good_time = """SELECT good_date(%s, localtimestamp)"""

        cursor.execute(sql_good_time, (start,))

        result = str(cursor.fetchone())[1:-1]

        if result == "False":
            cursor.close()
            connection.close()
            return 3

        # check if the member already has a booking for that time span

        sql_memberbusy = """SELECT member_busy(%s, %s, %s)"""

        cursor.execute(sql_memberbusy, (memid, start, end,))

        result = str(cursor.fetchone())[1:-1]

        if result == "True":
            cursor.close()
            connection.close()
            return 2

        # check if there is already a booking for that car intersecting the time period

        sql_carbusy = """SELECT car_busy(%s, %s, %s)"""

        cursor.execute(sql_carbusy, (car_rego, start, end,))

        result = str(cursor.fetchone())[1:-1]

        if result == "True":
            cursor.close()
            connection.close()
            return 1

        # update member's bookings count both in db and in session storage

        sql_memstat = """UPDATE Member
                         SET stat_nrOfBookings = stat_nrOfBookings + 1
                         WHERE email = %s"""

        cursor.execute(sql_memstat, (email,))

        # insert new booking into db

        sql_newbooking = """INSERT INTO Booking VALUES (DEFAULT, %s, %s, transaction_timestamp(), %s, %s);"""

        cursor.execute(sql_newbooking, (car_rego, memid, start, end,))

        connection.commit()
        cursor.close()
        connection.close()

        return 0

    except:
        print("ERROR CODE 03")
        connection.rollback()
        cursor.close()
        connection.close()

        return -1


def get_all_bookings(email):

    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_booking =     """SELECT A.regno, A.name, B.starttime::date, (EXTRACT(epoch FROM B.endtime - B.starttime) / 3600)::integer
                             FROM Car A INNER JOIN Booking B ON (A.regno = B.car) INNER JOIN MEMBER C ON (B.madeby = C.memberno)
                             WHERE C.email = %s
                             ORDER BY B.starttime DESC"""

        cursor.execute(sql_booking, (email,))

        result = cursor.fetchall()

        for row in result:
            val.append(list(row))

        cursor.close()
        connection.close()

    except:
        print("ERROR CODE 04")
        cursor.close()
        connection.close()

    return val

def get_booking(b_date, b_hour, car):

    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_booking =     """SELECT D.nametitle ||'. '|| D.namegiven||' '|| D.namefamily, A.regno, A.name, B.starttime::date, B.starttime::time, (EXTRACT(epoch FROM B.endtime - B.starttime) / 3600)::integer || 'h', B.whenbooked::date, C.name, E.hourly_rate, E.daily_rate, D.memberno
                             FROM Car A INNER JOIN Booking B ON (A.regno = B.car) INNER JOIN CarBay C ON (A.parkedat = C.bayid) INNER JOIN MEMBER D ON (B.madeby = D.memberno) INNER JOIN  MembershipPlan E ON (D.subscribed = E.title)
                             WHERE A.regno = %s AND  B.starttime::date = %s AND (EXTRACT(epoch FROM B.endtime - B.starttime) / 3600)::integer = %s"""

        cursor.execute(sql_booking, (car, b_date, b_hour,))
        val = list(cursor.fetchone())

        # check how many bookings have been made for today by this member

        sql_daily =     """SELECT COUNT(*)
                           FROM Booking 
                           WHERE starttime::date = %s AND madeby = %s"""

        cursor.execute(sql_daily, (b_date, val[10],))
        count = int(str(cursor.fetchone())[1:-1])


        # estimate base fees for booking
        val[8] = (int(val[8]) * int(val[5][:-1])) / 100
        val[9] = (int(val[9]) * count) / 100

        dur = '${:.2f}'.format(val[8])
        daily = '${:.2f}'.format(val[9])

        # format properly
        val[8] = "Hourly base estimate: "+dur+", Daily fee for today: "+daily+" (charged once for any bookings you have for this day)"

        cursor.close()
        connection.close()

    except:
        print("ERROR CODE 05")
        cursor.close()
        connection.close()

    return val

#####################################################
##  Car (Details and List)
#####################################################

def get_car_details(regno):

    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_car =     """SELECT A.regno, A.name, A.make, A.model, A.year, A.transmission, B.category, B.capacity, C.name, C.walkscore, C.mapurl
                         FROM Car A INNER JOIN CarModel B ON (A.make = B.make AND A.model = B.model)
                                    INNER JOIN CarBay C ON (A.parkedat = C.bayid)
                         WHERE regno = %s"""

        cursor.execute(sql_car, (regno,))
        val = list(cursor.fetchone())

        hours = []

        sql_free = """SELECT free_hour(%s, current_date, %s)"""
        hour = 0
        
        while (hour < 24):
            fhour = pg8000.Time(hour,0,0)
            cursor.execute(sql_free, (regno, fhour,))
            result = str(cursor.fetchone())[1:-1]
            if result == "False":
                hours.append(str(hour)+":00")
            hour += 1

        val.append(str(hours)[1:-1])

        cursor.close()
        connection.close()

    except pg8000.OperationalError as e:
        print("ERROR CODE 06")
        cursor.close()
        connection.close()

    return val

def get_all_cars():

    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_car =     """SELECT regno, name, make, model, year, transmission 
                         FROM Car"""

        cursor.execute(sql_car)

        result = cursor.fetchall()

        for row in result:
            val.append(list(row))

        cursor.close()
        connection.close()

    except:
        print("ERROR CODE 07")
        cursor.close()
        connection.close()

    return val

#####################################################
##  Bay (detail, list, finding cars inside bay)
#####################################################

def get_all_bays(homebay):
    
    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        # if the member has a homebay, list it first

        if homebay != 'Add a homebay':
            sql_bays = """SELECT name, address, cars_parked 
                          FROM Carbay
                          ORDER BY name = %s DESC, name"""

            cursor.execute(sql_bays, (homebay,))

        else:
            sql_bays = """SELECT name, address, cars_parked 
                          FROM Carbay
                          ORDER BY name"""
            cursor.execute(sql_bays)

        result = cursor.fetchall()

        for row in result:
            val.append(list(row))

        cursor.close()
        connection.close()

    except:
        print("ERROR CODE 08")
        cursor.close()
        connection.close()

    return val

def get_bay(name):

    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_homebay = """SELECT name, description, address, gps_lat, gps_long, bayid 
                         FROM Carbay
                         WHERE name = %s"""

        cursor.execute(sql_homebay, (name,))

        val = cursor.fetchone()

        cursor.close()
        connection.close()

    except:
        print("ERROR CODE 09")
        cursor.close()
        connection.close()

    return val

def search_bays(search_term):

    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_homebay = """SELECT name, address, cars_parked 
                         FROM Carbay
                         WHERE name ~* %s OR address ~* %s"""

        query_param = ".*"+search_term+".*"

        cursor.execute(sql_homebay, (query_param, query_param,))

        result = cursor.fetchall()

        for row in result:
            val.append(list(row))

        cursor.close()
        connection.close()

    except:
        print("ERROR CODE 10")
        cursor.close()
        connection.close()

    return val

def get_cars_in_bay(bay_id):

    val = []

    try:
        connection = database_connect()
        cursor = connection.cursor()

        sql_cars =    """SELECT regno, name 
                         FROM Car
                         WHERE parkedat = %s"""

        sql_carstatus = """SELECT car_status(%s, localtimestamp)"""

        cursor.execute(sql_cars, (bay_id,))

        result = cursor.fetchall()

        for row in result:
            val.append(list(row))

        for res in val:
            cursor.execute(sql_carstatus, (res[0],))
            result = str(cursor.fetchone())[1:-1]

            if result == "True":
                res.append("Later ;_;")
            else:
                res.append("Now!")

        cursor.close()
        connection.close()

    except pg8000.OperationalError as e:
        print(e)
        print("ERROR CODE 11")
        cursor.close()
        connection.close()

    return val
