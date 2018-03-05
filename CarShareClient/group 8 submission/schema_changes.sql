SET search_Path = CarSharing, '$user', public, unidb;

BEGIN TRANSACTION;

ALTER TABLE CarBay
ADD COLUMN cars_parked INTEGER;

-- Run for the first time
UPDATE CarBay 
         SET cars_parked = (SELECT COUNT(*)
                            FROM Car B
                            WHERE B.parkedat = bayid);

COMMIT;

CREATE OR REPLACE FUNCTION count_cars() RETURNS trigger AS 
$BODY$
   BEGIN
      UPDATE CarBay 
         SET cars_parked = (SELECT COUNT(*)
                              FROM Car B
                              WHERE B.parkedat = bayid);
         RETURN NEW;
   END;
$BODY$ LANGUAGE plpgsql;
ALTER FUNCTION count_cars()
  OWNER TO jkou5005;
  
CREATE trigger count_cars AFTER INSERT OR UPDATE ON Car
   FOR EACH STATEMENT EXECUTE PROCEDURE count_cars();


-- checks if a member has made a booking with an overlapping timeslot
CREATE OR REPLACE FUNCTION member_busy(memid int, start text, finish text) RETURNS BOOLEAN AS 
$$
   BEGIN      
    RETURN EXISTS (SELECT 1 
                     FROM Booking 
                     WHERE madeby = memid AND (
                     (starttime > start::timestamp AND starttime <= finish::timestamp) OR -- b starts before and finishes after or on a's start
                     (starttime < start::timestamp AND endtime >= finish::timestamp) OR -- b starts after a and finishes before or when a ends
                     (endtime >= start::timestamp AND endtime < finish::timestamp)  -- b starts before or when a finishes and finishes after a 
                     )
                     );
   END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION count_cars()
  OWNER TO jkou5005;

-- checks if the car has been booked in an overlapping timeslot
CREATE OR REPLACE FUNCTION car_busy(rego text, start text, finish text) RETURNS BOOLEAN AS 
$$
   BEGIN
      RETURN EXISTS (SELECT 1 
                     FROM Booking 
                     WHERE car = rego AND (
                     (starttime > start::timestamp AND starttime <= finish::timestamp) OR -- b starts before and finishes after or on a's start
                     (starttime < start::timestamp AND endtime >= finish::timestamp) OR -- b starts after a and finishes before or when a ends
                     (endtime >= start::timestamp AND endtime < finish::timestamp)  -- b starts before or when a finishes and finishes after a 
                     )
                     );
   END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION count_cars()
  OWNER TO jkou5005;

-- checks if the car is currently booked
CREATE OR REPLACE FUNCTION car_status(rego text, now timestamp) RETURNS BOOLEAN AS 
$$
   BEGIN
      RETURN EXISTS (SELECT 1 
                     FROM Booking 
                     WHERE car = rego AND (
                     (starttime < now AND endtime > now)
                     )
                     );
   END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION count_cars()
  OWNER TO jkou5005;

-- checks that the time is in the future
CREATE OR REPLACE FUNCTION good_date(start text, now timestamp) RETURNS BOOLEAN AS 
$$
   BEGIN
      RETURN start::timestamp > now;
   END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION count_cars()
  OWNER TO jkou5005;

-- returns whether the car is free for that hour
CREATE OR REPLACE FUNCTION free_hour(regno text, today date, hour time) RETURNS BOOLEAN AS 
$$
   BEGIN
      RETURN EXISTS (SELECT 1 
                     FROM Booking 
                     WHERE car = regno AND starttime::date = today AND (
                     starttime::time <= hour::time AND endtime::time >= hour::time
                     )
                     );
   END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION count_cars()
  OWNER TO jkou5005;
