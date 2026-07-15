import { NavigationContainer, useNavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import HomeScreen from './src/screens/HomeScreen';
import SplashScreen from './src/screens/SplashScreen';
import IntroScreen from './src/screens/IntroScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import PhoneFrame from './src/components/PhoneFrame';
import HomeIndicator from './src/components/HomeIndicator';
import { RecentItemsProvider } from './src/store/RecentItemsContext';
import ProfileScreen from './src/screens/ProfileScreen';
import VoiceRegisterScreen from './src/screens/VoiceRegisterScreen';
import VoiceRegisterRecordingScreen from './src/screens/VoiceRegisterRecordingScreen';
import BookReadingScreen from './src/screens/BookReadingScreen';
import LibraryScreen from './src/screens/LibraryScreen';
import LullabySingingScreen from './src/screens/LullabySingingScreen';
import BookPlaybackScreen from './src/screens/BookPlaybackScreen';
import LullabyPlaybackScreen from './src/screens/LullabyPlaybackScreen';
import { VoiceProfileProvider } from './src/store/VoiceProfileContext';

const Stack = createNativeStackNavigator();

export default function App() {
    const navigationRef = useNavigationContainerRef();

    const goHome = () => {
        navigationRef.reset({ index: 0, routes: [{ name: 'Home' }] });
    };

    return (
        <RecentItemsProvider>
            <VoiceProfileProvider>
                <PhoneFrame>
                    <NavigationContainer ref={navigationRef}>
                        <Stack.Navigator initialRouteName="Home" screenOptions={{ headerShown: false }}>
                            <Stack.Screen name="Home" component={HomeScreen} />
                            <Stack.Screen name="Splash" component={SplashScreen} />
                            <Stack.Screen name="Intro" component={IntroScreen} />
                            <Stack.Screen name="Dashboard" component={DashboardScreen} />
                            <Stack.Screen name="Profile" component={ProfileScreen} />
                            <Stack.Screen name="VoiceRegister" component={VoiceRegisterScreen} />
                            <Stack.Screen name="VoiceRegisterRecording" component={VoiceRegisterRecordingScreen} />
                            <Stack.Screen name="BookReading" component={BookReadingScreen} />
                            <Stack.Screen name="Library" component={LibraryScreen} />
                            <Stack.Screen name="LullabySinging" component={LullabySingingScreen} />
                            <Stack.Screen name="BookPlayback" component={BookPlaybackScreen} />
                            <Stack.Screen name="LullabyPlayback" component={LullabyPlaybackScreen} />
                        </Stack.Navigator>
                    </NavigationContainer>
                    <HomeIndicator onPress={goHome} />
                </PhoneFrame>
            </VoiceProfileProvider>
        </RecentItemsProvider>
    );
}