import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import BottomNav from '../components/BottomNav';
import { useVoiceProfile } from '../store/VoiceProfileContext';
import { useEffect, useState } from 'react';

export default function ProfileScreen({ navigation }) {
  const { profile } = useVoiceProfile();

  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0); // 0~1

  useEffect(() => {
    if (!isPlaying) return undefined;
    const totalSeconds = 3.5 * 60;
    const id = setInterval(() => {
      setProgress((prev) => {
        const next = prev + 1 / totalSeconds;
        if (next >= 1) {
          clearInterval(id);
          setIsPlaying(false);
          return 1;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [isPlaying]);

  const togglePlay = () => {
    if (progress >= 1) setProgress(0);
    setIsPlaying((prev) => !prev);
  };

  return (
      <View style={styles.container}>
        <StatusBar barStyle="dark-content" />
        <SafeAreaView style={styles.safe} edges={['top']}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => navigation.goBack()} style={styles.headerSide}>
              <Ionicons name="chevron-back" size={20} color="#575757" />
            </TouchableOpacity>
            <Text style={styles.headerTitle}>프로필</Text>
            <View style={styles.headerSide} />
          </View>

          <View style={styles.content}>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>내 목소리 프로필</Text>

              <View style={styles.profileRow}>
                <View style={styles.avatar}>
                  <Ionicons name="mic" size={22} color="#6071e7" />
                </View>
                <View>
                  <Text style={styles.profileName}>{profile.name}</Text>
                  <Text style={styles.profileDate}>{profile.date} 생성</Text>
                </View>
              </View>

              <View style={styles.divider} />

              <Text style={styles.previewLabel}>미리듣기</Text>
              <View style={styles.previewRow}>
                <TouchableOpacity style={styles.playBtn} onPress={togglePlay}>
                  <Ionicons name={isPlaying ? 'pause' : 'play'} size={16} color="#6071e7" />
                </TouchableOpacity>
                <View style={styles.progressTrack}>
                  <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
                </View>
                <Text style={styles.duration}>{profile.duration}</Text>
              </View>
            </View>

            <TouchableOpacity
                style={styles.regenerateBtn}
                onPress={() => navigation.navigate('VoiceRegister')}
            >
              <Text style={styles.regenerateText}>다시 생성하기</Text>
            </TouchableOpacity>
          </View>

          <BottomNav navigation={navigation} active="profile" />
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
  content: { flex: 1, paddingHorizontal: 16, paddingTop: 20 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 18 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: '#000' },
  profileRow: { flexDirection: 'row', alignItems: 'center', gap: 15, marginTop: 17 },
  avatar: {
    width: 57, height: 57, borderRadius: 16,
    backgroundColor: '#cdd3ff', alignItems: 'center', justifyContent: 'center',
  },
  profileName: { fontSize: 18, fontWeight: '600', color: '#000' },
  profileDate: { fontSize: 16, fontWeight: '400', color: '#7d7d7d', marginTop: 4 },
  divider: { height: 1, backgroundColor: '#e3e3e3', marginTop: 25 },
  previewLabel: { fontSize: 16, fontWeight: '600', color: '#000', marginTop: 17 },
  previewRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12 },
  playBtn: {
    width: 37, height: 37, borderRadius: 19,
    backgroundColor: '#e3e3e3', alignItems: 'center', justifyContent: 'center',
  },
  progressTrack: { flex: 1, height: 10, borderRadius: 45, backgroundColor: '#e3e3e3', overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 45, backgroundColor: '#6071e7' },
  duration: { fontSize: 12, fontWeight: '500', color: '#575757' },
  regenerateBtn: {
    marginTop: 34, height: 55, borderRadius: 8,
    backgroundColor: '#d8ddff', alignItems: 'center', justifyContent: 'center',
  },
  regenerateText: { fontSize: 20, fontWeight: '600', color: '#6071e7' },
});