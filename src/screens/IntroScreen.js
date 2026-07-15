import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function IntroScreen({ navigation }) {
    return (
        <LinearGradient
            colors={['#96a3ff', '#6071e7']}
            start={{ x: 0.1, y: 0 }}
            end={{ x: 0.85, y: 1 }}
            style={styles.container}
        >
            <StatusBar barStyle="light-content" />
            <SafeAreaView style={styles.safe}>
                <View style={styles.body}>
                    <Text style={styles.logo}>담음</Text>
                    <Text style={styles.tagline}>부모와 감정과 목소리를 담음</Text>
                </View>
                <View style={styles.ctaWrap}>
                    <TouchableOpacity style={styles.cta} onPress={() => navigation.navigate('Profile')}>
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
    body: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 30 },
    logo: { fontSize: 56, fontWeight: '800', color: '#fff' },
    tagline: { marginTop: 24, fontSize: 20, fontWeight: '600', color: '#fff' },
    ctaWrap: { paddingHorizontal: 24, paddingBottom: 36 },
    cta: {
        backgroundColor: '#fff',
        height: 55,
        borderRadius: 8,
        alignItems: 'center',
        justifyContent: 'center',
    },
    ctaText: { color: '#6071e7', fontSize: 18, fontWeight: '600' },
});