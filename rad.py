from __future__ import print_function
import os
import sys
import datetime
import ftplib
import shutil
import subprocess
import numpy as np
import pylab as plt
import healpy as hp
from astropy import units as u
from astropy import constants as c
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, Angle, Latitude, Longitude

# Defining some variables for further use
### Make the base path settable
base_path = os.path.expanduser('~/radionopy')
TECU = 1e16
TEC2m2 = 0.1 * TECU
earth_radius = c.R_earth.value #6371000.0 # in meters
tesla_to_gauss = 1e4

def IONEX_file_needed(year, month, day):
    time_str = '{year} {month} {day}'.format(year=year, month=month, day=day)
    day_of_year = datetime.datetime.strptime(time_str, '%Y %m %d').timetuple().tm_yday

    if day_of_year < 10:
        day_of_year = '00{day_of_year}'.format(day_of_year=day_of_year)
    elif 10 <= day_of_year < 100:
        day_of_year = '0{day_of_year}'.format(day_of_year=day_of_year)

    # Outputing the name of the IONEX file you require
    ionex_file = 'CODG{day_of_year}0.{year_end}I'.format(day_of_year=day_of_year, year_end=str(year)[2:4])
    ionex_file_z = ''.join((ionex_file, '.Z'))

    if not os.path.exists(ionex_file) and not os.path.exists(ionex_file_z):
        ionex_file_z = get_IONEX_file(ionex_file, year, month, day)
        subprocess.call(['uncompress', ionex_file_z])

    return ionex_file

def get_IONEX_file(IONEX_file, year, month, day):
    server = 'ftp.unibe.ch'

    ftp_dir = os.path.join('aiub/CODE/', year)
    IONEX_file_Z = ''.join((IONEX_file, '.Z'))
 
    getting_file_str = 'Retrieving {IONEX_file_Z} for {day} {month} {year}'.format(IONEX_file_Z=IONEX_file_Z, day=day, month=month, year=year)
    print(getting_file_str)

    try:
        ftp = ftplib.FTP(server, 'anonymous', 'jaguirre@sas.upenn.edu')
        ftp.cwd(ftp_dir)
        ftp.retrbinary(' '.join(('RETR', IONEX_file_Z)), open(IONEX_file_Z, 'wb').write)
        ftp.quit()
    except:
        os.remove(IONEX_file_Z)

    return IONEX_file_Z

def gen_IONEX_list(IONEX_list):
    add = False
    rms_add = False
    base_IONEX_list = []
    RMS_IONEX_list = []
    for file_data in IONEX_list[:-1]:
        if not file_data:
            continue
        if file_data.split()[-2:] == ['RMS', 'MAP']:
            add = False
            rms_add = True
        elif file_data.split()[-2:] == ['IN', 'FILE']:
            number_of_maps = float(file_data.split()[0])

        if file_data.split()[0] == 'END' and file_data.split()[2] == 'HEADER':
            add = True

        if rms_add:
            RMS_IONEX_list.append(file_data)
        if add:
            base_IONEX_list.append(file_data)

        if file_data.split()[-1] == 'DHGT':
            ion_h = float(file_data.split()[0])
        elif file_data.split()[-1] == 'DLAT':
            start_lat, end_lat, step_lat = [float(data_item) for data_item in file_data.split()[:3]]
        elif file_data.split()[-1] == 'DLON':
            start_lon, end_lon, step_lon = [float(data_item) for data_item in file_data.split()[:3]]

    return base_IONEX_list, RMS_IONEX_list, number_of_maps, ion_h, start_lat, end_lat, step_lat, start_lon, end_lon, step_lon

def read_IONEX_TEC(filename):
    #==========================================================================
    # Reading and storing only the TEC values of 1 day
    # (13 maps) into a 3D array

    # Opening and reading the IONEX file into memory
    with open(filename, 'r') as read_file:
        linestring = read_file.read()
        IONEX_list = linestring.split('\n')

    # creating a new array without the header and only
    # with the TEC maps
    base_IONEX_list, RMS_IONEX_list, number_of_maps, ion_h,\
    start_lat, end_lat, step_lat,\
    start_lon, end_lon, step_lon = gen_IONEX_list(IONEX_list)

    # Variables that indicate the number of points in Lat. and Lon.
    points_lat = ((end_lat - start_lat) / step_lat) + 1
    points_lon = ((end_lon - start_lon) / step_lon) + 1

    print(start_lat, end_lat, step_lat)
    print(start_lon, end_lon, step_lon)
    print(points_lat, points_lon)

    # What are the Lat/Lon coords?
    latitude = np.linspace(start_lat, end_lat, num=points_lat)
    longitude = np.linspace(start_lon, end_lon, num=points_lon)

    TEC_list = []
    # Selecting only the TEC values to store in the 3-D array
    for new_IONEX_list in (base_IONEX_list, RMS_IONEX_list):
        # 3D array that will contain TEC values only
        a = np.zeros((number_of_maps, points_lat, points_lon))

        counter_maps = 1
        for i in range(len(new_IONEX_list)):
            # Pointing to first map (out of 13 maps)
            # then by changing 'counter_maps' the other
            # maps are selected
            if new_IONEX_list[i].split()[0] == str(counter_maps) and new_IONEX_list[i].split()[-4] == 'START':
                # pointing the starting latitude
                # then by changing 'counter_lat' we select
                # TEC data at other latitudes within
                # the selected map
                counter_lat = 0
                new_start_lat = float(str(start_lat))
                for item_lat in range(int(points_lat)):
                    if new_IONEX_list[i + 2 + counter_lat].split()[0].split('-')[0] == str(new_start_lat)\
                    or '-' + new_IONEX_list[i + 2 + counter_lat].split()[0].split('-')[1] == str(new_start_lat):
                        # Adding to array 'a' a line of latitude TEC data
                        # we account for the TEC values at negative latitudes
                        counter_lon = 0
                        for count_num in range(3, 8):
                            list_index = i + count_num + counter_lat
                            for new_IONEX_item in new_IONEX_list[list_index].split():
                                a[counter_maps - 1, item_lat, counter_lon] = new_IONEX_item
                                counter_lon = counter_lon + 1
                    counter_lat = counter_lat + 6
                    new_start_lat = new_start_lat + step_lat
                counter_maps = counter_maps + 1

        TEC_list.append({'TEC': np.array(a), 'a': a})

    tec_a = TEC_list[0]['a']
    rms_a = TEC_list[1]['a']
    TEC =  {'TEC': TEC_list[0]['TEC'], 'lat': latitude, 'lon': longitude}
    RMS_TEC =  {'TEC': TEC_list[1]['TEC'], 'lat': latitude, 'lon': longitude}
    
    return TEC, RMS_TEC, (start_lat, step_lat, points_lat, start_lon, step_lon, points_lon, number_of_maps, tec_a, rms_a, ion_h * 1000.0)
    #==========================================================================

def interp_time(points_lat, points_lon, number_of_maps, total_maps, a):
    time_count = 1.0
    #==========================================================================================
    # producing interpolated TEC maps, and consequently a new array that will 
    # contain 25 TEC maps in total. The interpolation method used is the second
    # one indicated in the IONEX manual

    # creating a new array that will contain 25 maps in total 
    newa = np.zeros((total_maps, points_lat, points_lon))
    inc = 0
    for item in range(int(number_of_maps)):
        newa[inc, :, :] = a[item, :, :]
        inc = inc + 2

    # performing the interpolation to create 12 addional maps 
    # from the 13 TEC maps available
    time_int = int(time_count)
    while time_int <= (total_maps - 2):
        for lon in range(int(points_lon)):
            # interpolation type 2:
            # newa[int(time_count), :, lon] = 0.5 * newa[int(time_count) - 1, :, lon] + 0.5 * newa[int(time_count) + 1, :, lon]
            # interpolation type 3 ( 3 or 4 columns to the right and left of the odd maps have values of zero
            # Correct for this):
            #if (lon >= 4) and (lon <= (points_lon - 4)):
            #    newa[time_int, :, lon] = 0.5 * newa[time_int - 1, :, lon + 3] + 0.5 * newa[time_int + 1, :, lon - 3] 
            newa[time_int, :, lon] = 0.5 * newa[time_int - 1, :, (lon + 3) % int(points_lon)] + 0.5 * newa[time_int + 1, :, lon - 3] 
        time_int = time_int + 2

    return newa

def punct_ion_offset(lat_obs, az_src, zen_src, ion_height):
    #earth_radius = 6371000.0 # in meters

    # The 2-D sine rule gives the zenith angle at the
    # Ionospheric piercing point
    zen_punct = np.arcsin((earth_radius * np.sin(zen_src)) / (earth_radius + ion_height)) 

    # Use the sum of the internal angles of a triange to determine theta
    theta = zen_src - zen_punct

    # The cosine rule for spherical triangles gives us the latitude
    # at the IPP
    lat_ion = np.arcsin(np.sin(lat_obs) * np.cos(theta) + np.cos(lat_obs) * np.sin(theta) * np.cos(az_src)) 
    off_lat = lat_ion - lat_obs # latitude difference

    # Longitude difference using the 3-D sine rule (or for spherical triangles)
    off_lon = np.arcsin(np.sin(az_src) * np.sin(theta) / np.cos(lat_ion))

    # Azimuth at the IPP using the 3-D sine rule
    s_az_ion = np.sin(az_src) * np.cos(lat_obs) / np.cos(lat_ion)
    az_punct = np.arcsin(s_az_ion)

    return off_lat, off_lon, az_punct, zen_punct

def get_coords(lat_str, lon_str, lat_obs, lon_obs, off_lat, off_lon):
    if lat_str[-1] == 's':
        lat_val = -1
    elif lat_str[-1] == 'n':
        lat_val = 1
    if lon_str[-1] == 'e':
        lon_val = 1
    elif lon_str[-1] == 'w':
        lon_val = -1

    coord_lat = lat_val * (lat_obs.value + off_lat)
    coord_lon = lon_val * (lon_obs.value + off_lon)

    return coord_lat, coord_lon

def tecs2hp(lat, lon, tec_map, rms_map):
    nlat = len(lat)
    nlon = len(lon)
    lat_rad = np.outer(np.radians(90. - lat), np.ones(nlon))
    lon_rad = np.outer(np.ones(nlat), np.radians(lon % 360))

    nside = 16
    tec_hp = healpixellize(tec_map, lat_rad, lon_rad, nside)
    rms_hp = healpixellize(rms_map, lat_rad, lon_rad, nside)

    return tec_hp, rms_hp

def interp_space(TEC, RMS_TEC, UT, coord_lat, coord_lon, zen_punct, newa, rmsa):
    tec_hp, rms_hp = tecs2hp(TEC['lat'], TEC['lon'], newa[UT], rmsa[UT])

    lat_rad = np.radians(90. - coord_lat)
    lon_rad = np.radians(coord_lon % 360)
    VTEC = hp.get_interp_val(tec_hp, lat_rad, lon_rad)
    VRMS_TEC = hp.get_interp_val(rms_hp, lat_rad, lon_rad)

    TEC_path = np.array(VTEC) * TEC2m2 / np.cos(zen_punct) # from vertical TEC to line of sight TEC
    RMS_TEC_path = np.array(VRMS_TEC) * TEC2m2 / np.cos(zen_punct) # from vertical RMS_TEC to line of sight RMS_TEC

    return TEC_path, RMS_TEC_path

def B_IGRF(year, month, day, coord_lat, coord_lon, ion_height, az_punct, zen_punct):
    # Calculation of TEC path value for the indicated 'hour' and therefore 
    # at the IPP

    input_file = os.path.join(base_path, 'IGRF/geomag70_linux/input.txt')
    output_file = os.path.join(base_path, 'IGRF/geomag70_linux/output.txt')

    #uses lat_val, lon_val from above
    # Calculation of the total magnetic field along the line of sight at the IPP
    with open(input_file, 'w') as f:
        for co_lat, co_lon in zip(coord_lat, coord_lon):
            f.write('{year},{month},{day} C K{sky_rad} {ipp_lat} {ipp_lon}\n'.format(year=year, month=month, day=day,
                                                                                   sky_rad=(earth_radius + ion_height) / 1000.0,
                                                                                   ipp_lat=co_lat, ipp_lon=co_lon))

    #XXX runs the geomag exe script
    script_name = os.path.join('./', base_path, 'IGRF/geomag70_linux/geomag70')
    script_data = os.path.join(base_path, 'IGRF/geomag70_linux/IGRF11.COF')
    script_option = 'f'
    subprocess.call([script_name, script_data, script_option, input_file, output_file])

    B_para = []
    with open(output_file, 'r') as g:
        all_data = g.readlines()

        for i, data in enumerate(all_data[1:]):
            x_field, y_field, z_field = [abs(float(field_data)) * 1e-9 * tesla_to_gauss for field_data in data.split()[10:13]]
            B_paras = z_field * np.cos(zen_punct[i]) +\
                      y_field * np.sin(zen_punct[i]) * np.sin(az_punct[i]) +\
                      x_field * np.sin(zen_punct[i]) * np.cos(az_punct[i])

            B_para.append(B_paras)

    return np.array(B_para)

def get_results(hour, TEC_path, RMS_TEC_path, B_para):
    # Saving the Ionosheric RM and its corresponding
    # rms value to a file for the given 'hour' value
    IFR = 2.6e-17 * B_para * TEC_path
    RMS_IFR = 2.6e-17 * B_para * RMS_TEC_path

    new_file = os.path.join(base_path, 'RM_files', 'IonRM{hour}.txt'.format(hour=hour))
    with open(new_file, 'w') as f:
        for tp, tf, ifr, rms_ifr in zip(TEC_path, B_para, IFR, RMS_IFR):
            f.write(('{hour} {TEC_path} '
                     '{B_para} {IFR} '
                     '{RMS_IFR}\n').format(hour=hour,
                                           TEC_path=tp,
                                           B_para=tf,
                                           IFR=ifr,
                                           RMS_IFR=rms_ifr))

def healpixellize(f_in, theta_in, phi_in, nside, fancy=True):
    ''' A dumb method for converting data f sampled at points theta and phi (not on a healpix grid) into a healpix at resolution nside '''

    # Input arrays are likely to be rectangular, but this is inconvenient
    f = f_in.flatten()
    theta = theta_in.flatten()
    phi = phi_in.flatten()

    pix = hp.ang2pix(nside, theta, phi)

    hp_map = np.zeros(hp.nside2npix(nside))
    hits = np.zeros(hp.nside2npix(nside))
    
    # Simplest gridding is hp_map[pix] = val. This tries to do some
    #averaging Better would be to do some weighting by distance from
    #pixel center or something ...
    if fancy:
        for i, v in enumerate(f):
            # Find the nearest pixels to the pixel in question
            #neighbours, weights = hp.get_neighbours(nside, theta[i], phi[i])
            neighbours, weights = hp.get_interp_weights(nside, theta[i], phi[i])
            # Add weighted values to hp_map
            hp_map[neighbours] += v * weights
            # Keep track of weights
            hits[neighbours] += weights
        hp_map = hp_map / hits
        wh_no_hits = np.where(hits == 0)
        print('pixels with no hits', wh_no_hits[0].shape)
        hp_map[wh_no_hits[0]] = hp.UNSEEN
    else:    
        for i, v in enumerate(f):
            hp_map[pix[i]] += v
            hits[pix[i]] += 1
        hp_map = hp_map / hits

    wh = np.where(hp_map == np.nan)[0]
    for i, w in enumerate(wh):
        neighbors = hp.get_interp_weights(nside, theta[i], phi[i])
        hp_map[w] = np.median(neighbors)

    return hp_map

def std_hour(UT):
    print(int(UT))
    if UT < 10:
        hour = '0{hour}'.format(hour=int(UT))
    else:
        hour = '{hour}'.format(hour=int(UT))

    return hour

if __name__ == '__main__':
    # PAPER INFO
    nside = 16
    npix = hp.nside2npix(nside)
    ipix = np.arange(npix)
    theta, phi = hp.pix2ang(nside, ipix)

    alt = 90. - np.degrees(np.array(theta))
    az = np.degrees(np.array(phi))

    lat_str = '30d43m17.5ss'
    lon_str = '21d25m41.9se'
    time_str = '2012-02-13T00:00:00'
    #IONEX_file = 'CODG0440.12I'
    height = 1000

    #

    year, month, day = time_str.split('T')[0].split('-')
    IONEX_file = IONEX_file_needed(year, month, day)
    IONEX_name = os.path.join(base_path, IONEX_file)

    lat_obs = Latitude(Angle(lat_str[:-1]))
    lon_obs = Longitude(Angle(lon_str[:-1]))

    start_time = Time(time_str)
    #lat is negative because it's south
    location = EarthLocation(lat=-lat_obs, lon=lon_obs, height=height * u.m)

    TEC, RMS_TEC, all_info = read_IONEX_TEC(IONEX_name)

    _, _, points_lat, _, _, points_lon, number_of_maps, a, rms_a, ion_height = all_info

    newa = interp_time(points_lat, points_lon, number_of_maps, 25, a)
    rmsa = interp_time(points_lat, points_lon, number_of_maps, 25, rms_a)

    zen = np.degrees(np.array(theta))
    off_lat, off_lon, az_punct, zen_punct = punct_ion_offset(lat_obs.radian, np.radians(az), np.radians(zen), ion_height)
    coord_lat, coord_lon = get_coords(lat_str, lon_str, lat_obs, lon_obs, np.degrees(off_lat), np.degrees(off_lon))

    B_para = B_IGRF(year, month, day, coord_lat, coord_lon, ion_height, az_punct, zen_punct)

    # predict the ionospheric RM for every hour within a day 
    UTs = np.linspace(0, 23, num=24)
    
    for UT in UTs:
        hour = std_hour(UT)    
        TEC_path, RMS_TEC_path = interp_space(TEC, RMS_TEC, UT, coord_lat, coord_lon, zen_punct, newa, rmsa)

        #results = {'TEC': TEC, 'RMS_TEC': RMS_TEC, 'IFR': IFR, 'RMS_IFR': RMS_IFR, 'B_para': B_para}
        get_results(hour, TEC_path, RMS_TEC_path, B_para)
