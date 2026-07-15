import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function IntroScreen({ navigation }) {
    return (
        <LinearGradient
            colors={['#8f95f4', '#6d74ec', '#5a61e0']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.container}
        >
            <StatusBar barStyle="light-content" />
            <SafeAreaView style={styles.safe}>
                <View style={styles.body}>
                    <Text style={styles.logo}>담음</Text>
                    <Text style={styles.tagline}>부모와 감정과 목소리를 담음</Text>
                </View>

                <View style={styles.ctaWrap}>
                    <TouchableOpacity
                        style={styles.cta}
                        onPress={() => navigation.navigate('Dashboard')}
                    >
                        <Text style={styles.ctaText}>시작하기</Text>
                    </TouchableOpacity>
                </View>
            </SafeAreaView>
        </LinearGradient>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1 },
    safe: { flex: 1 },
    body: {
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 30,
    },
    logo: {
        fontSize: 52,
        fontWeight: '800',
        color: '#fff',
        letterSpacing: -1,
    },
    tagline: {
        marginTop: 14,
        fontSize: 15,
        fontWeight: '500',
        color: 'rgba(255,255,255,0.9)',
    },
    ctaWrap: {
        paddingHorizontal: 26,
        paddingBottom: 30,
    },
    cta: {
        backgroundColor: '#fff',
        paddingVertical: 16,
        borderRadius: 16,
        alignItems: 'center',
    },
    ctaText: {
        color: '#4c4fc9',
        fontSize: 15,
        fontWeight: '700',
    },
});