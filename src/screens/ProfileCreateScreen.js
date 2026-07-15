import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const STATUS_ROWS = [
    { label: '발병 전 음성', value: '미완료' },
    { label: '현재 음성', value: '0 / 5 문장' },
    { label: '가족 기증 음색', value: '선택 사항' },
];

export default function ProfileCreateScreen({ navigation }) {
    return (
        <View style={styles.outer}>
            <SafeAreaView style={styles.card} edges={['top', 'bottom']}>
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => navigation.goBack()} style={styles.headerSide}>
                        <Text style={styles.backArrow}>{'<'}</Text>
                    </TouchableOpacity>
                    <Text style={styles.headerTitle}>프로필 생성</Text>
                    <View style={styles.headerSide} />
                </View>

                <ScrollView contentContainerStyle={styles.body}>
                    <Text style={styles.h1}>목소리 프로필 만들기</Text>
                    <Text style={styles.p}>
                        아이에게 전해질 목소리를 담아주세요. 샘플은 안전하게 저장되며 언제든 삭제할 수 있습니다.
                    </Text>

                    <Text style={styles.h2}>현재 음성 녹음</Text>
                    <Text style={styles.p}>지금 목소리를 직접 녹음합니다. 아래 문장을 천천히 읽어주세요.</Text>

                    <View style={styles.panel}>
                        <View style={styles.skeletonBar} />
                        <TouchableOpacity style={styles.darkBtn}>
                            <Text style={styles.darkBtnText}>녹음 시작</Text>
                        </TouchableOpacity>
                        <Text style={styles.p}>0 / 5 문장 완료</Text>
                    </View>

                    <View style={styles.panel}>
                        <Text style={styles.h3}>샘플 충족 상태</Text>
                        {STATUS_ROWS.map((row) => (
                            <View key={row.label} style={styles.statusRow}>
                                <Text style={styles.p}>{row.label}</Text>
                                <View style={styles.statusLine} />
                                <Text style={styles.p}>{row.value}</Text>
                            </View>
                        ))}
                        <Text style={styles.p}>최소 5문장 이상을 완료하면 프로필을 생성할 수 있습니다.</Text>
                    </View>

                    <View style={styles.checkboxRow}>
                        <View style={styles.checkbox} />
                        <Text style={styles.checkboxLabel}>
                            수집된 음성 데이터는 목소리 합성에만 사용되며, 언제든 삭제 요청이 가능합니다.
                        </Text>
                    </View>

                    <TouchableOpacity
                        style={styles.darkBtn}
                        onPress={() => navigation.navigate('Dashboard')}
                    >
                        <Text style={styles.darkBtnText}>프로필 생성하기</Text>
                    </TouchableOpacity>
                </ScrollView>
            </SafeAreaView>
        </View>
    );
}

const TEXT_MAIN = '#1f2937';
const BORDER = '#e5e7eb';

const styles = StyleSheet.create({
    outer: { flex: 1, backgroundColor: '#fff' },
    card: {
        flex: 1,
        backgroundColor: '#fff',
        borderWidth: 3,
        borderColor: '#ff0004',
        borderRadius: 12,
        overflow: 'hidden',
    },
    header: {
        flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
        paddingHorizontal: 24, paddingVertical: 12,
        borderBottomWidth: 1, borderBottomColor: '#d0d0d0',
    },
    headerSide: { width: 20, alignItems: 'center' },
    backArrow: { fontSize: 20, color: TEXT_MAIN },
    headerTitle: { flex: 1, textAlign: 'center', fontSize: 16, fontWeight: '500', color: TEXT_MAIN },
    body: { padding: 24, gap: 16 },
    h1: { fontSize: 16, fontWeight: '600', color: TEXT_MAIN },
    h2: { fontSize: 20, fontWeight: '700', color: TEXT_MAIN },
    h3: { fontSize: 16, fontWeight: '600', color: TEXT_MAIN },
    p: { fontSize: 12, fontWeight: '400', color: TEXT_MAIN },
    panel: {
        backgroundColor: '#f9fafb',
        borderWidth: 1, borderColor: BORDER,
        borderRadius: 6, padding: 13, gap: 12,
    },
    skeletonBar: { width: 117, height: 11, borderRadius: 4, backgroundColor: BORDER },
    darkBtn: {
        backgroundColor: TEXT_MAIN,
        borderRadius: 6, paddingHorizontal: 16, paddingVertical: 8,
        alignSelf: 'flex-start',
    },
    darkBtnText: { color: '#fff', fontSize: 14, fontWeight: '500' },
    statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    statusLine: { flex: 1, height: 1, backgroundColor: 'transparent' },
    checkboxRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
    checkbox: {
        width: 16, height: 16, borderRadius: 3,
        borderWidth: 1.5, borderColor: '#d1d5db', backgroundColor: '#fff',
    },
    checkboxLabel: { flex: 1, fontSize: 14, fontWeight: '400', color: TEXT_MAIN },
});