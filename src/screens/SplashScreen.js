import { useEffect } from 'react';
import { View, Text, StyleSheet, StatusBar } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export default function SplashScreen({ navigation }) {
    useEffect(() => {
        const timer = setTimeout(() => {
            navigation.replace('Intro');
        }, 1100);
        return () => clearTimeout(timer);
    }, [navigation]);

    return (
        <LinearGradient
            colors={['#96a3ff', '#6071e7']}
            start={{ x: 0.1, y: 0 }}
            end={{ x: 0.85, y: 1 }}
            style={styles.container}
        >
            <StatusBar barStyle="light-content" />
            <View style={styles.center}>
                <Text style={styles.logo}>담음</Text>
            </View>
        </LinearGradient>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1 },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
    logo: { fontSize: 56, fontWeight: '800', color: '#fff' },
});