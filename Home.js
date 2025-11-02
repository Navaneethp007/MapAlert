import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Vibration,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  Animated,
  Platform,
  StatusBar,
} from 'react-native';
import MapView, { Marker, Circle } from 'react-native-maps';
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';

const HomeScreen = () => {
  const [location, setLocation] = useState(null);
  const [destination, setDestination] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [distance, setDistance] = useState(null);
  const [isTracking, setIsTracking] = useState(false);
  const [hasAlerted, setHasAlerted] = useState(false);
  
  const mapRef = useRef(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const locationSubscription = useRef(null);

  // Pulse animation for current location
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.3,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, []);

  // Request location permissions and get initial location
  useEffect(() => {
    (async () => {
      setIsLoading(true);
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setErrorMsg('Permission to access location was denied');
        setIsLoading(false);
        return;
      }

      let { coords } = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      setLocation(coords);
      setIsLoading(false);
    })();

    return () => {
      if (locationSubscription.current) {
        locationSubscription.current.remove();
      }
    };
  }, []);

  // Start/Stop tracking
  useEffect(() => {
    if (isTracking && destination) {
      startLocationTracking();
    } else {
      stopLocationTracking();
    }

    return () => stopLocationTracking();
  }, [isTracking, destination]);

  // Calculate distance when location or destination changes
  useEffect(() => {
    if (location && destination) {
      const dist = calculateDistance(location, destination);
      setDistance(dist);

      // Alert if within 2km and haven't alerted yet
      if (dist <= 2 && !hasAlerted) {
        triggerProximityAlert(dist);
        setHasAlerted(true);
      } else if (dist > 2.5) {
        // Reset alert flag when far enough away
        setHasAlerted(false);
      }
    }
  }, [location, destination]);

  const startLocationTracking = async () => {
    try {
      // Request background permissions
      const { status } = await Location.requestBackgroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(
          'Background Permission Required',
          'Please enable background location to track your journey.'
        );
        setIsTracking(false);
        return;
      }

      locationSubscription.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.High,
          timeInterval: 10000, // Update every 10 seconds
          distanceInterval: 50, // Or every 50 meters
        },
        (newLocation) => {
          setLocation(newLocation.coords);
        }
      );
    } catch (error) {
      console.error('Error starting location tracking:', error);
      Alert.alert('Error', 'Failed to start location tracking');
      setIsTracking(false);
    }
  };

  const stopLocationTracking = () => {
    if (locationSubscription.current) {
      locationSubscription.current.remove();
      locationSubscription.current = null;
    }
  };

  const calculateDistance = (c1, c2) => {
    const lat1 = c1.latitude;
    const lon1 = c1.longitude;
    const lat2 = c2.latitude;
    const lon2 = c2.longitude;
    const p = 0.017453292519943295;
    const c = Math.cos;
    const a =
      0.5 -
      c((lat2 - lat1) * p) / 2 +
      (c(lat1 * p) * c(lat2 * p) * (1 - c((lon2 - lon1) * p))) / 2;

    return 12742 * Math.asin(Math.sqrt(a));
  };

  const triggerProximityAlert = (dist) => {
    const distanceKm = dist.toFixed(2);
    Vibration.vibrate([500, 200, 500, 200, 500]);
    
    Alert.alert(
      '🎯 Destination Nearby!',
      `You are ${distanceKm} km away from your destination!`,
      [
        {
          text: 'Got it!',
          style: 'default',
        },
      ]
    );
  };

  const handleMapPress = (event) => {
    const coords = event.nativeEvent.coordinate;
    setDestination(coords);
    setHasAlerted(false);
    
    // Animate to show both locations
    if (mapRef.current && location) {
      mapRef.current.fitToCoordinates([location, coords], {
        edgePadding: { top: 100, right: 50, bottom: 300, left: 50 },
        animated: true,
      });
    }
  };

  const handleSearch = async () => {
    if (!searchText.trim()) {
      Alert.alert('Error', 'Please enter a location to search');
      return;
    }

    setIsLoading(true);
    try {
      const geocode = await Location.geocodeAsync(searchText);
      if (geocode && geocode.length > 0) {
        const coords = {
          latitude: geocode[0].latitude,
          longitude: geocode[0].longitude,
        };
        setDestination(coords);
        setHasAlerted(false);
        
        // Animate to searched location
        if (mapRef.current && location) {
          mapRef.current.fitToCoordinates([location, coords], {
            edgePadding: { top: 100, right: 50, bottom: 300, left: 50 },
            animated: true,
          });
        }
      } else {
        Alert.alert('Not Found', 'Location not found. Please try again.');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to search location. Please try again.');
    }
    setIsLoading(false);
  };

  const clearDestination = () => {
    setDestination(null);
    setDistance(null);
    setIsTracking(false);
    setHasAlerted(false);
    setSearchText('');
  };

  const centerOnLocation = () => {
    if (mapRef.current && location) {
      mapRef.current.animateToRegion({
        latitude: location.latitude,
        longitude: location.longitude,
        latitudeDelta: 0.05,
        longitudeDelta: 0.05,
      });
    }
  };

  const toggleTracking = () => {
    if (!destination) {
      Alert.alert('No Destination', 'Please select a destination first');
      return;
    }
    setIsTracking(!isTracking);
  };

  if (errorMsg) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle" size={64} color="#ff6b6b" />
        <Text style={styles.errorText}>{errorMsg}</Text>
      </View>
    );
  }

  if (isLoading && !location) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4A90E2" />
        <Text style={styles.loadingText}>Loading your location...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar barStyle="dark-content" />
      
      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={20} color="#666" style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search for a location..."
            onChangeText={setSearchText}
            value={searchText}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
          />
          {searchText.length > 0 && (
            <TouchableOpacity onPress={() => setSearchText('')}>
              <Ionicons name="close-circle" size={20} color="#999" />
            </TouchableOpacity>
          )}
        </View>
        <TouchableOpacity 
          style={styles.searchButton} 
          onPress={handleSearch}
          disabled={isLoading}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Ionicons name="arrow-forward" size={20} color="#fff" />
          )}
        </TouchableOpacity>
      </View>

      {/* Map */}
      <MapView
        ref={mapRef}
        style={styles.map}
        onPress={handleMapPress}
        showsUserLocation={false}
        showsMyLocationButton={false}
        initialRegion={{
          latitude: location?.latitude ?? 10.0558,
          longitude: location?.longitude ?? 76.6183,
          latitudeDelta: 0.0922,
          longitudeDelta: 0.0421,
        }}
      >
        {/* Current Location Marker */}
        {location && (
          <>
            <Circle
              center={location}
              radius={2000}
              strokeColor="rgba(74, 144, 226, 0.3)"
              fillColor="rgba(74, 144, 226, 0.1)"
            />
            <Marker coordinate={location} anchor={{ x: 0.5, y: 0.5 }}>
              <Animated.View style={[styles.currentLocationMarker, {
                transform: [{ scale: pulseAnim }]
              }]}>
                <View style={styles.currentLocationInner} />
              </Animated.View>
            </Marker>
          </>
        )}

        {/* Destination Marker */}
        {destination && (
          <Marker
            coordinate={destination}
            title="Destination"
            description={distance ? `${distance.toFixed(2)} km away` : ''}
          >
            <View style={styles.destinationMarker}>
              <Ionicons name="location" size={40} color="#E74C3C" />
            </View>
          </Marker>
        )}
      </MapView>

      {/* Info Card */}
      {destination && distance !== null && (
        <View style={styles.infoCard}>
          <View style={styles.distanceContainer}>
            <Ionicons name="navigate" size={24} color="#4A90E2" />
            <View style={styles.distanceTextContainer}>
              <Text style={styles.distanceLabel}>Distance to destination</Text>
              <Text style={styles.distanceValue}>
                {distance.toFixed(2)} km
              </Text>
            </View>
          </View>
          
          <View style={styles.actionButtons}>
            <TouchableOpacity
              style={[styles.trackButton, isTracking && styles.trackingActive]}
              onPress={toggleTracking}
            >
              <Ionicons 
                name={isTracking ? "pause" : "play"} 
                size={20} 
                color="#fff" 
              />
              <Text style={styles.trackButtonText}>
                {isTracking ? 'Stop Tracking' : 'Start Tracking'}
              </Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={styles.clearButton}
              onPress={clearDestination}
            >
              <Ionicons name="close" size={20} color="#E74C3C" />
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Floating Action Buttons */}
      <View style={styles.fabContainer}>
        <TouchableOpacity
          style={styles.fab}
          onPress={centerOnLocation}
        >
          <Ionicons name="locate" size={24} color="#4A90E2" />
        </TouchableOpacity>
      </View>

      {/* Status Indicator */}
      {isTracking && (
        <View style={styles.trackingIndicator}>
          <View style={styles.trackingDot} />
          <Text style={styles.trackingText}>Tracking active</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  map: {
    width: '100%',
    height: '100%',
  },
  searchContainer: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 60 : 40,
    left: 20,
    right: 20,
    zIndex: 10,
    flexDirection: 'row',
    alignItems: 'center',
  },
  searchBox: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 15,
    paddingVertical: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 5,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: '#333',
  },
  searchButton: {
    backgroundColor: '#4A90E2',
    borderRadius: 12,
    padding: 12,
    marginLeft: 10,
    width: 48,
    height: 48,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#4A90E2',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 5,
  },
  currentLocationMarker: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: 'rgba(74, 144, 226, 0.3)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  currentLocationInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#4A90E2',
    borderWidth: 2,
    borderColor: '#fff',
  },
  destinationMarker: {
    alignItems: 'center',
  },
  infoCard: {
    position: 'absolute',
    bottom: 30,
    left: 20,
    right: 20,
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  distanceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 15,
  },
  distanceTextContainer: {
    marginLeft: 12,
    flex: 1,
  },
  distanceLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  distanceValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  actionButtons: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  trackButton: {
    flex: 1,
    backgroundColor: '#4A90E2',
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  trackingActive: {
    backgroundColor: '#E74C3C',
  },
  trackButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  clearButton: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E74C3C',
  },
  fabContainer: {
    position: 'absolute',
    right: 20,
    bottom: 200,
  },
  fab: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#fff',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 5,
  },
  trackingIndicator: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 120 : 100,
    alignSelf: 'center',
    backgroundColor: '#E74C3C',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 5,
  },
  trackingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#fff',
    marginRight: 8,
  },
  trackingText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f8f9fa',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f8f9fa',
    padding: 40,
  },
  errorText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
});

export default HomeScreen;