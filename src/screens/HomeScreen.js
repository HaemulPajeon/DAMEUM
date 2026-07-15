import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';

const DAYS = ['일', '월', '화', '수', '목', '금', '토'];

function formatBig(date) {
    let h12 = date.getHours() % 12;
    if (h12 === 0) h12 = 12;
    const m = date.getMinutes().toString().padStart(2, '0');
    return `${h12}:${m}`;
}
function formatDate(date) {
    return `${date.getMonth() + 1}월 ${date.getDate()}일 ${DAYS[date.getDay()]}요일`;
}

export default function HomeScreen({ navigation }) {
    const [now, setNow] = useState(new Date());
    useEffect(() => {
        const id = setInterval(() => setNow(new Date()), 15000);
        return () => clearInterval(id);
    }, []);

    return (
        <LinearGradient colors={['#c6c5f0', '#8f95f4', '#5a61e0']} style={styles.container}>
            <StatusBar barStyle="light-content" />
            <SafeAreaView style={styles.safe}>
                <View style={styles.clockWrap}>
                    <Text style={styles.time}>{formatBig(now)}</Text>
                    <Text style={styles.date}>{formatDate(now)}</Text>
                </View>

                <View style={styles.grid}>
                    <TouchableOpacity style={styles.slot} onPress={() => navigation.navigate('Splash')}>
                        <View style={styles.icon}>
                            <Text style={styles.iconGlyph}>♥</Text>
                        </View>
                        <Text style={styles.label}>담음</Text>
                    </TouchableOpacity>
                </View>
            </SafeAreaView>
        </LinearGradient>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1 },
    safe: { flex: 1 },
    clockWrap: { alignItems: 'center', marginTop: 90 },
    time: { fontSize: 60, fontWeight: '700', color: '#232244', letterSpacing: -1 },
    date: { fontSize: 15, fontWeight: '600', color: '#4c4fc9', marginTop: 6 },
    grid: { marginTop: 60, paddingHorizontal: 24 },
    slot: { alignItems: 'center', width: 74, gap: 6 },
    icon: {
        width: 60, height: 60, borderRadius: 16,
        backgroundColor: '#4c4fc9',
        alignItems: 'center', justifyContent: 'center',
    },
    iconGlyph: { fontSize: 24, color: '#fff' },
    label: { fontSize: 12, fontWeight: '700', color: '#232244' },
});