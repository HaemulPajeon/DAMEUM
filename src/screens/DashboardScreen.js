import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';

const NAV_ITEMS = [
    { key: 'home', label: '홈', icon: 'home' },
    { key: 'library', label: '라이브러리', icon: 'grid' },
    { key: 'book', label: '동화책', icon: 'add-circle' },
    { key: 'lullaby', label: '자장가', icon: 'moon' },
    { key: 'profile', label: '프로필', icon: 'person' },
];

export default function DashboardScreen() {
    return (
        <LinearGradient
            colors={['#d3d8ff', 'rgba(195,203,255,0.4)', 'rgba(206,212,255,0.15)']}
            locations={[0, 0.42, 1]}
            style={styles.container}
        >
            <StatusBar barStyle="dark-content" />
            <SafeAreaView style={styles.safe} edges={['top']}>
                <View style={styles.content}>
                    <Text style={styles.greeting}>
                        안녕하세요.{'\n'}오늘도 <Text style={styles.greetingAccent}>아이와 연결</Text>되어 보세요
                    </Text>

                    <Text style={styles.sectionTitle}>이어서 들어요</Text>
                    <View style={styles.continueCard}>
                        <Text style={styles.continueTitle}>
                            잠자리 토끼 <Text style={styles.continueSub}>어제 재생</Text>
                        </Text>
                        <TouchableOpacity style={styles.playBtn}>
                            <Text style={styles.playBtnText}>재생</Text>
                        </TouchableOpacity>
                    </View>

                    <View style={styles.actionGrid}>
                        <TouchableOpacity style={styles.actionCardBlue}>
                            <View>
                                <Text style={styles.actionTitle}>새 동화책 담음</Text>
                                <Text style={styles.actionSubBlue}>동화책을 녹음하기</Text>
                            </View>
                            <MaterialCommunityIcons name="book-open-page-variant" size={34} color="#7d88e8" style={styles.actionIcon} />
                        </TouchableOpacity>

                        <TouchableOpacity style={styles.actionCardCream}>
                            <View>
                                <Text style={styles.actionTitle}>자장가 담음</Text>
                                <Text style={styles.actionSubCream}>자장가 녹음하기</Text>
                            </View>
                            <Ionicons name="musical-notes" size={30} color="#d9b043" style={styles.actionIcon} />
                        </TouchableOpacity>
                    </View>

                    <Text style={styles.sectionTitle}>최근 읽은 책이에요</Text>
                    <View style={styles.recentCard}>
                        <Text style={styles.recentTitle}>
                            잠자리 토끼 <Text style={styles.recentMeta}>5페이지・7/10</Text>
                        </Text>
                        <Ionicons name="chevron-forward" size={17} color="#848484" />
                    </View>
                </View>

                <View style={styles.bottomNav}>
                    {NAV_ITEMS.map((item, idx) => (
                        <TouchableOpacity key={item.key} style={styles.navItem}>
                            <Ionicons name={item.icon} size={21} color={idx === 0 ? '#6071e7' : '#575757'} />
                            <Text style={[styles.navLabel, idx === 0 && styles.navLabelActive]}>{item.label}</Text>
                        </TouchableOpacity>
                    ))}
                </View>
            </SafeAreaView>
        </LinearGradient>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1 },
    safe: { flex: 1 },
    content: { flex: 1, justifyContent: 'center', paddingHorizontal: 20 },
    greeting: { fontSize: 21, fontWeight: '600', color: '#373737', lineHeight: 28 },
    greetingAccent: { color: '#6071e7', fontWeight: '700' },
    sectionTitle: { marginTop: 22, marginBottom: 10, fontSize: 18, fontWeight: '600', color: '#373737' },
    continueCard: {
        flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
        backgroundColor: '#96a3ff',
        borderWidth: 1, borderColor: '#c7ceff',
        borderRadius: 15, height: 78, paddingHorizontal: 16,
    },
    continueTitle: { fontSize: 17, fontWeight: '600', color: '#fff' },
    continueSub: { fontSize: 13, fontWeight: '500', color: '#e4e8ff' },
    playBtn: { backgroundColor: '#6071e7', paddingHorizontal: 16, paddingVertical: 9, borderRadius: 8 },
    playBtnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
    actionGrid: { flexDirection: 'row', gap: 12, marginTop: 12 },
    actionCardBlue: {
        flex: 1, height: 175, borderRadius: 10, padding: 14, justifyContent: 'space-between',
        backgroundColor: '#e4e7ff',
        borderWidth: 1, borderColor: '#c4ccff',
    },
    actionCardCream: {
        flex: 1, height: 175, borderRadius: 10, padding: 14, justifyContent: 'space-between',
        backgroundColor: '#fff9e6',
        borderWidth: 1, borderColor: '#fff1c0',
    },
    actionTitle: { fontSize: 15, fontWeight: '700', color: '#454545' },
    actionSubBlue: { fontSize: 11.5, fontWeight: '500', color: '#9f9f9f', marginTop: 2 },
    actionSubCream: { fontSize: 11.5, fontWeight: '500', color: '#909090', marginTop: 2 },
    actionIcon: { alignSelf: 'flex-end' },
    recentCard: {
        marginTop: 12, backgroundColor: '#fff', borderRadius: 15,
        borderWidth: 1, borderColor: '#dedede',
        height: 68, paddingHorizontal: 16,
        flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    },
    recentTitle: { fontSize: 17, fontWeight: '600', color: '#3d3d3a' },
    recentMeta: { fontSize: 13, fontWeight: '400', color: '#848484' },
    bottomNav: {
        backgroundColor: '#fff',
        borderTopWidth: 0.6, borderTopColor: '#dfe2e1',
        flexDirection: 'row', justifyContent: 'space-around',
        paddingTop: 10, paddingBottom: 14,
    },
    navItem: { alignItems: 'center', gap: 3 },
    navLabel: { fontSize: 12, fontWeight: '500', color: '#575757' },
    navLabelActive: { color: '#6071e7' },
});