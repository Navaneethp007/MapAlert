import React, {useState,useEffect} from 'react';
import { StyleSheet, View, Text, Vibration, Button, TextInput, TouchableOpacity } from 'react-native';
import { Icon } from 'react-native-vector-icons/FontAwesome';
import MapView,{Marker} from 'react-native-maps';
import * as Location from 'expo-location';

const HomeScreen = () => {
  const [location, setLocation] = useState(null);
  const [mcoords, setMcoords] = useState(null);
  const [scoords, setScoords] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [searchtext, setSearchtext] = useState('');
  useEffect(() => {
    (async () => {
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setErrorMsg('Permission to access location was denied');
        return;
      }
      let { coords } = await Location.getCurrentPositionAsync({});
      setLocation(coords);
    })();
  }, []);
  useEffect(() => {
    if(location && mcoords){
      const distance = calculateDistance(location,mcoords);
      const distance2 = calculateDistance(location,scoords);
      if(distance<=2 || distance2<=2)
      {
        Vibration.vibrate([1000, 500, 1000]);
        alert("Da Mandaaaa, STHALAM EHTARAYI!!!!!");
      }
      //setShowVib(false);
    }
  },[location,mcoords]);
  const handlecord=(event)=>{
    setMcoords(event.nativeEvent.coordinate);
  }
  const handleSearch=(text)=>{
    setSearchtext(text);
  }
  const calculateDistance=(c1, c2)=>{
    const lat1 = c1.latitude;
    const lon1 = c1.longitude;
    const lat2 = c2.latitude;
    const lon2 = c2.longitude;
    const p = 0.017453292519943295;
    const c = Math.cos;
    const a = 0.5 - c((lat2 - lat1) * p)/2 + 
              c(lat1 * p) * c(lat2 * p) * 
              (1 - c((lon2 - lon1) * p))/2;
  
    return 12742 * Math.asin(Math.sqrt(a));
  }
  const geocode = async () => {
    let geocode = await Location.geocodeAsync(searchtext);
    setScoords(geocode[0]);
  }
  return (
    <View>
    <TextInput
      style={{ marginTop:40, marginBottom:40, zIndex: 1, backgroundColor: 'white', padding: 10, width: '100%', position: 'absolute', top: 0, left: 0}}
      placeholder="Type Here..."
      onChangeText={handleSearch}
      value={searchtext}
  />
  <TouchableOpacity style={{position: 'absolute', top: 60, right: 0, zIndex: 1, backgroundColor: 'white', padding: 10}} onPress={geocode}>
    <Text>Search</Text>
  </TouchableOpacity>
    {errorMsg ? (
      <Text>{errorMsg}</Text>
    ) : (
       console.log(location)
    )}
      <MapView
        style={styles.map}
        onPress={handlecord}
        initialRegion={{
          latitude: location ?.latitude??10.0558,
          longitude: location ?.longitude??76.6183,
          latitudeDelta: 0.0922,
          longitudeDelta: 0.0421,
        }}
      >
        {location && (
  <Marker
    coordinate={location}
    title="Current Location"
    description="This is your current location"
  />
        )}
{mcoords && (
  <Marker
    coordinate={mcoords}
    title="Selected Location"
    description="This is your selected location"
    />
)}
{scoords && (
  <Marker
    coordinate={scoords}
    title="Searched Location"
    description="This is your searched location"
    />
)}
      </MapView>
          
      </View>
  );
};

const styles = StyleSheet.create({
  
  map: {
    width: '100%',
    height: '100%'
  },
  
});

export default HomeScreen;
