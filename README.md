# MapAlert 🌍📍

## Overview

**MapAlert** is a mobile application built with **React Native** and **Expo** that provides real-time alerts when users are **2 km away from their selected destination**. The app also allows users to **search for locations**, with markers placed at selected destinations.

## 🚀 Features

- **📌 Location Search**
  - Users can search for places and drop a marker at their destination.
  - Intuitive search interface for easy location finding.

- **🚨 Proximity Alert System**
  - Compares the distance between the user's current location and their selected destination.
  - Triggers an **alert when the user is within 2 km** of their destination.
  - Device vibrates in a distinct pattern (500ms, 200ms, 500ms, 200ms, 500ms) to notify users.

- **📱 Cross-platform Support**
  - Works seamlessly on both iOS and Android devices.
  - Built with React Native and Expo for maximum compatibility.

- **🗺️ Interactive Maps**
  - Powered by React Native Maps.
  - Real-time location tracking.
  - Custom markers and annotations.

## 🔄 How It Works

1. **Search/Select for a Location**
   - Users enter a place name, and a marker is placed on the map.

2. **Start Tracking**
   - The app continuously updates the user's location in the background.

3. **Trigger Alert**
   - When the distance between the user's current coordinates and the selected destination drops **below 2 km**:
     - Visual alert is displayed
     - Phone vibrates to notify the user
     - Distance to destination is shown

## 📂 Project Structure

```plaintext
MapAlert/
├── assets/            # Static assets and images
├── App.js            # Main application component
├── Home.js           # Home screen with map functionality
├── index.js          # Entry point
├── app.json          # Expo configuration
└── package.json      # Project dependencies and scripts
```

## 🛠️ Technologies Used

- React Native
- Expo Framework
- React Native Maps
- Expo Location
- @expo/vector-icons
- React Native Safe Area Context
- React Native Vibration API

## ⚙️ Setup and Installation

### Prerequisites

- Node.js (v14 or higher)
- npm or pnpm
- Expo CLI: `npm install -g expo-cli`
- iOS: Xcode & Simulator (for Mac users)
- Android: Android Studio & Emulator

### Installation Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/Navaneethp007/MapAlert.git
   cd MapAlert
   ```

2. Install dependencies:

   ```bash
   pnpm install
   # or
   npm install
   ```

## 🚀 Running the Application

Start the development server:

```bash
pnpm start
# or
npm start
```

### Android Development

```bash
pnpm android
# or
npm run android
```

### iOS Development

```bash
pnpm ios
# or
npm run ios
```

Note: For iOS testing, you have two options:

1. Build the app and test it on a physical device
2. Use the pre-built version in an iOS simulator via Xcode

### Web Development

```bash
pnpm web
# or
npm run web
```

## 🏗️ Building for Production

### Android Build

1. Configure your app.json
2. Run the build command:

   ```bash
   eas build -p android
   ```

### iOS Build

1. Configure your app.json
2. Run the build command:

   ```bash
   eas build -p ios
   ```

