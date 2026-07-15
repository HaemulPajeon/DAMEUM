import { useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

function parseSeconds(mmss) {
  if (!mmss || !mmss.includes(':')) return 180;
  const [m, s] = mmss.split(':').map(Number);
  return (m || 0) * 60 + (s || 0);
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function LullabyPlaybackScreen({ route, navigation }) {
  const item = route?.params?.item;
  const title = item?.title || '자장가';
  const totalSeconds = useMemo(() => parseSeconds(item?.meta), [item]);

  // TODO(백엔드 연동): item.playableUrl이 있으면 api.fetchAuthedMediaUrl로 실제 오디오를
  // 받아 expo-av Audio.Sound로 재생. 지금은 녹음 파이프라인이 없어 진행률만 시뮬레이션.
  const [isPlaying, setIsPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [repeat, setRepeat] = useState(false);
  const [sleepTimer, setSleepTimer] = useState(false);

  useEffect(() => {
    if (!isPlaying) return undefined;
    const id = setInterval(() => {
      setElapsed((prev) => {
        if (prev + 1 >= totalSeconds) {
          if (repeat) return 0;
          setIsPlaying(false);
          return totalSeconds;
        }
        return prev + 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [isPlaying, repeat, totalSeconds]);

  const progressRatio = totalSeconds > 0 ? Math.min(elapsed / totalSeconds, 1) : 0;

  return (
    <View style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.headerSide}>
            <Ionicons name="chevron-back" size={20} color="#575757" />
          </TouchableOpacity>
          <Text style={styles.headerBackLabel}>뒤로가기</Text>
          <TouchableOpacity onPress={() => navigation.navigate('Library')}>
            <Text style={styles.endLink}>종료</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.badgeWrap}>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>자장가</Text>
          </View>
        </View>

        <Text style={styles.title}>{title}</Text>

        <View style={styles.artWrap}>
          <View style={styles.artOuter}>
            <View style={styles.artInner}>
              <Ionicons name="musical-notes" size={48} color="#6071e7" />
            </View>
          </View>
        </View>

        <View style={styles.progressWrap}>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${progressRatio * 100}%` }]} />
          </View>
          <View style={styles.progressLabels}>
            <Text style={styles.timeLabel}>
              {formatTime(elapsed).slice(0, 2)}:
              <Text style={styles.timeLabelActive}>{formatTime(elapsed).slice(3)}</Text>
            </Text>
            <Text style={styles.timeLabel}>{formatTime(totalSeconds)}</Text>
          </View>
        </View>

        <TouchableOpacity style={styles.playBtn} onPress={() => setIsPlaying((prev) => !prev)}>
          <Ionicons name={isPlaying ? 'pause' : 'play'} size={30} color="#6071e7" />
        </TouchableOpacity>

        <View style={styles.optionRow}>
          <TouchableOpacity
            style={[styles.optionBtn, repeat ? styles.optionBtnActive : styles.optionBtnInactive]}
            onPress={() => setRepeat((prev) => !prev)}
          >
            <Text style={repeat ? styles.optionTextActive : styles.optionTextInactive}>반복 재생</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.optionBtn, sleepTimer ? styles.optionBtnActive : styles.optionBtnInactive]}
            onPress={() => setSleepTimer((prev) => !prev)}
          >
            <Text style={sleepTimer ? styles.optionTextActive : styles.optionTextInactive}>20분 후 끄기</Text>
          </TouchableOpacity>
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
  headerBackLabel: { position: 'absolute', left: 46, fontSize: 18, fontWeight: '600', color: '#575757' },
  endLink: { fontSize: 18, fontWeight: '600', color: '#6071e7' },
  badgeWrap: { alignItems: 'center', marginTop: 44 },
  badge: {
    backgroundColor: '#6071e7', borderRadius: 45,
    height: 30, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center',
  },
  badgeText: { fontSize: 18, fontWeight: '600', color: '#fff' },
  title: { fontSize: 28, fontWeight: '700', color: '#1f2937', textAlign: 'center', marginTop: 20 },
  artWrap: { alignItems: 'center', marginTop: 40 },
  artOuter: {
    width: 185, height: 185, borderRadius: 93,
    backgroundColor: '#eceeff', alignItems: 'center', justifyContent: 'center',
  },
  artInner: {
    width: 151, height: 151, borderRadius: 76,
    backgroundColor: '#dfe3ff', alignItems: 'center', justifyContent: 'center',
  },
  progressWrap: { paddingHorizontal: 16, marginTop: 44 },
  progressTrack: { height: 12, borderRadius: 45, backgroundColor: '#d9d9d9', overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 45, backgroundColor: '#6071e7' },
  progressLabels: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 9 },
  timeLabel: { fontSize: 20, fontWeight: '400', color: '#848484' },
  timeLabelActive: { color: '#6071e7' },
  playBtn: {
    alignSelf: 'center', marginTop: 32,
    width: 87, height: 87, borderRadius: 44,
    backgroundColor: '#dfe3ff',
    alignItems: 'center', justifyContent: 'center',
  },
  optionRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, marginTop: 'auto', marginBottom: 32 },
  optionBtn: { flex: 1, height: 55, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  optionBtnActive: { backgroundColor: '#6071e7' },
  optionBtnInactive: { backgroundColor: '#d8ddff' },
  optionTextActive: { fontSize: 20, fontWeight: '600', color: '#fff' },
  optionTextInactive: { fontSize: 20, fontWeight: '600', color: '#6071e7' },
});
