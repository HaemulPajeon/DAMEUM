import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useVoiceProfile } from '../store/VoiceProfileContext';

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function VoiceRegisterRecordingScreen({ navigation }) {
  const [elapsed, setElapsed] = useState(0);
  const { setProfile } = useVoiceProfile();

  useEffect(() => {
    const id = setInterval(() => setElapsed((prev) => prev + 1), 1000);
    return () => clearInterval(id);
  }, []);
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

          <TouchableOpacity
              style={styles.doneBtn}
              onPress={() => {
                setProfile({ name: '민수님의 목소리', duration: '00:00' });
                navigation.navigate('Profile');
              }}
          >
            <Text style={styles.doneText}>다 읽었어요</Text>
          </TouchableOpacity>

          <View style={styles.recordArea}>
            <Text style={styles.timer}>{formatElapsed(elapsed)}</Text>

            <View style={styles.circleOuter}>
              <View style={styles.circleInner}>
                <Ionicons name="pause" size={40} color="#6071e7" />
              </View>
            </View>

            <Text style={styles.hint}>녹음중이에요.</Text>
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
    height: 101, paddingTop: 44, backgroundColor: '#fff',
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
  doneBtn: {
    marginTop: 16, height: 55, width: 180, borderRadius: 8,
    backgroundColor: '#6071e7', alignItems: 'center', justifyContent: 'center',
    alignSelf: 'center',
  },
  doneText: { fontSize: 20, fontWeight: '600', color: '#fff' },
  recordArea: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 26 },
  timer: { fontSize: 20, fontWeight: '600', color: '#6071e7' },
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
