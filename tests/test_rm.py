'''
radiono.tests.test_rm

authors | Immanuel Washington, Saul Kohn

purpose | Script used to test IonoMap class in rm.py
'''
from __future__ import print_function
import unittest, os, shutil, random
from radiono import rm
import healpy as hp, numpy as np
from matplotlib import pyplot as plt

paperLocStrings = ('30d43m17.5ss','21d25m41.9se')
testIonexDir = './localIonex'
testRmDir = './localRM'
testHeight = 1000
testTime='2010-01-21'
testRA = [np.random.uniform(-np.pi/2.,np.pi/2.)]
testDec= [np.random.uniform(-np.pi/2.,np.pi/2.)]

testRAs,testDecs=np.random.uniform(-np.pi/2.,np.pi/2.,size=(hp.nside2npix(16))),np.random.uniform(-np.pi/2.,np.pi/2.,size=(hp.nside2npix(16)))

class TestIonoMap(unittest.TestCase):
    def setUp(self):
        self.rm_map = rm.IonoMap(paperLocStrings[0], paperLocStrings[1], [testTime], height=testHeight,\
        ionex_dir=testIonexDir, rm_dir=testRmDir)
    def test_map_properties(self):
        self.assertEqual(self.rm_map.lat.value, -30.721527777777776)
        self.assertEqual(self.rm_map.lon.value, 21.428305555555557)
        self.assertEqual(self.rm_map.height, testHeight)
        
        self.assertEqual(np.around(self.rm_map.location.latitude.value,5), np.around(-30.721527777777776,5))
        self.assertEqual(np.around(self.rm_map.location.longitude.value,5), np.around(21.428305555555557,5))
        self.assertEqual(np.around(self.rm_map.location.height.value,5), np.around(testHeight,5))    
    
        self.assertEqual(self.rm_map.rm_dir, testRmDir)
        self.assertEqual(self.rm_map.ionex_dir, testIonexDir)
    
    def test_make_rm_dir(self):
        self.rm_map.make_rm_dir(testTime)
        assert(os.path.exists(testRmDir+'/2010-01-21'))
    
    def test_ionex_data(self):
        tec_hp,rms_hp,ion_height = self.rm_map.ionex_data(2010,01,21,ionex_dir=testIonexDir)
        assert(tec_hp.shape == rms_hp.shape)
        assert(tec_hp.shape[0]==24)
        hp.npix2nside(tec_hp.shape[1])
        assert(ion_height > self.rm_map.location.height.value)
    
    def test_altaz(self):
        rm_altaz_map = self.rm_map.altaz()
    
    def test_radec_single(self):
        rm_radec_map = self.rm_map.get_radec_RM(testRA,testDec)           
    
    def test_radec_multip(self):
        rm_radec_map = self.rm_map.get_radec_RM(testRAs,testDecs)

    def tearDown(self):
        if os.path.exists(testRmDir): shutil.rmtree(testRmDir)
        if os.path.exists(testIonexDir): shutil.rmtree(testIonexDir)
        return None 


if __name__ == '__main__':
    unittest.main()
