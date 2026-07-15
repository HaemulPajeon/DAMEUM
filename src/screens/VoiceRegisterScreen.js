import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

export default function VoiceRegisterScreen({ navigation }) {
  return (
    <View style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.headerSide}>
            <Ionicons name="chevron-back" size={20} color="#575757" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>목소리 등록</Text>
          <View style={styles.headerSide} />
        </View>

        <View style={styles.content}>
          <View style={styles.card}>
            <Text style={styles.instruction}>아래 문장을 평소 말투 그대로 편하게 읽어주세요.</Text>
            <Text style={styles.sentence}>
              며칠 뒤 배고픈 늑대가{'\n'}첫째 돼지의 초가집 앞에{'\n'}나타났어요.
            </Text>
          </View>

          <View style={styles.recordArea}>
            <Text style={styles.timer}>00:00</Text>

            <TouchableOpacity
              style={styles.circleOuter}
              onPress={() => navigation.navigate('VoiceRegisterRecording')}
            >
              <View style={styles.circleInner}>
                <Ionicons name="mic" size={44} color="#6071e7" />
              </View>
            </TouchableOpacity>

            <Text style={styles.hint}>아래 녹음 버튼을 눌르면 시작되요.</Text>
          </View>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f6ff' },
  safe: { flex: 1 },
  header: {
    height: 57, backgroundColor: '#fff',
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 21,
  },
  headerSide: { width: 22 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: '#575757' },
  content: { flex: 1, paddingHorizontal: 16, paddingTop: 17 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 14, alignItems: 'center' },
  instruction: { fontSize: 16, fontWeight: '500', color: '#6071e7', alignSelf: 'flex-start' },
  sentence: {
    marginTop: 25, fontSize: 28, fontWeight: '700', color: '#353535',
    textAlign: 'center', lineHeight: 38,
  },
  recordArea: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 26 },
  timer: { fontSize: 20, fontWeight: '500', color: '#848484' },
  circleOuter: {
    width: 162, height: 162, borderRadius: 81,
    backgroundColor: '#eceeff', alignItems: 'center', justifyContent: 'center',
  },
  circleInner: {
    width: 132, height: 132, borderRadius: 66,
    backgroundColor: '#dfe3ff', alignItems: 'center', justifyContent: 'center',
  },
  hint: { fontSize: 20, fontWeight: '500', color: '#848484' },
});
