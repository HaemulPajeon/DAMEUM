import { useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

function parsePageCount(meta) {
  const match = meta?.match(/(\d+)\s*페이지/);
  return match ? Number(match[1]) : 1;
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

const PAGE_DURATION_SECONDS = 180;
const PAGE_TEXTS = [
  '며칠 뒤 배고픈 늑대가 첫째 돼지의 초가집 앞에 나타났어요.',
  '숲속 친구들이 하나 둘 모여들었어요',
  '조용히 자장가가 흘러나오기 시작했어요',
];

export default function BookPlaybackScreen({ route, navigation }) {
  const item = route?.params?.item;
  const title = item?.title || '동화책';
  const pageCount = useMemo(() => parsePageCount(item?.meta), [item]);

  // TODO(백엔드 연동): api.getPlaybackManifest(item.id)로 실제 페이지별 텍스트/이미지/오디오
  // URL을 받아와야 함. 지금은 녹음 파이프라인이 없어 페이지 이동/타이머만 시뮬레이션.
  const [currentPage, setCurrentPage] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isPlaying) return undefined;
    const id = setInterval(() => {
      setElapsed((prev) => (prev + 1 >= PAGE_DURATION_SECONDS ? PAGE_DURATION_SECONDS : prev + 1));
    }, 1000);
    return () => clearInterval(id);
  }, [isPlaying]);

  const progressRatio = elapsed / PAGE_DURATION_SECONDS;
  const pageText = PAGE_TEXTS[(currentPage - 1) % PAGE_TEXTS.length];

  const goPrev = () => {
    if (currentPage <= 1) return;
    setCurrentPage((prev) => prev - 1);
    setElapsed(0);
    setIsPlaying(false);
  };

  const goNext = () => {
    if (currentPage >= pageCount) return;
    setCurrentPage((prev) => prev + 1);
    setElapsed(0);
    setIsPlaying(false);
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.headerSide}>
            <Ionicons name="chevron-back" size={20} color="#575757" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>{title}</Text>
          <TouchableOpacity onPress={() => navigation.navigate('Library')}>
            <Text style={styles.endLink}>종료</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.badgeWrap}>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>동화책</Text>
          </View>
        </View>

        <Text style={styles.currentPageLabel}>현재 페이지</Text>
        <Text style={styles.pageNumber}>
          {currentPage}
          <Text style={styles.pageTotal}>/{pageCount} 페이지</Text>
        </Text>

        <View style={styles.pageCard}>
          <View style={styles.pageCardHeader}>
            <Ionicons name="alert-circle-outline" size={16} color="#848484" />
            <Text style={styles.pageCardHeaderText}>녹음된 음성 기반 텍스트에요</Text>
          </View>
          <Text style={styles.pageText}>{pageText}</Text>
        </View>

        <View style={styles.progressWrap}>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${Math.min(progressRatio, 1) * 100}%` }]} />
          </View>
          <View style={styles.progressLabels}>
            <Text style={styles.timeLabel}>
              {formatTime(elapsed).slice(0, 2)}:
              <Text style={styles.timeLabelActive}>{formatTime(elapsed).slice(3)}</Text>
            </Text>
            <Text style={styles.timeLabel}>{formatTime(PAGE_DURATION_SECONDS)}</Text>
          </View>
        </View>

        <View style={styles.controlsWrap}>
          <View style={styles.controlsRow}>
            <TouchableOpacity style={styles.sideBtn} onPress={goPrev} disabled={currentPage <= 1}>
              <Ionicons name="play-skip-back" size={30} color={currentPage <= 1 ? '#d9d9d9' : '#6071e7'} />
            </TouchableOpacity>
            <TouchableOpacity style={styles.playBtn} onPress={() => setIsPlaying((prev) => !prev)}>
              <Ionicons name={isPlaying ? 'pause' : 'play'} size={30} color="#6071e7" />
            </TouchableOpacity>
            <TouchableOpacity style={styles.sideBtn} onPress={goNext} disabled={currentPage >= pageCount}>
              <Ionicons name="play-skip-forward" size={30} color={currentPage >= pageCount ? '#d9d9d9' : '#6071e7'} />
            </TouchableOpacity>
          </View>
          <View style={styles.controlsLabelRow}>
            <Text style={styles.controlsLabel}>이전 페이지</Text>
            <Text style={styles.controlsLabel}>다음 페이지</Text>
          </View>
        </View>

        <Text style={styles.hint}>페이지를 넘긴 뒤 '다음 페이지'를 누르세요</Text>
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
  endLink: { fontSize: 18, fontWeight: '600', color: '#6071e7' },
  badgeWrap: { alignItems: 'center', marginTop: 20 },
  badge: {
    backgroundColor: '#6071e7', borderRadius: 45,
    height: 30, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center',
  },
  badgeText: { fontSize: 18, fontWeight: '600', color: '#fff' },
  currentPageLabel: { textAlign: 'center', fontSize: 14, fontWeight: '500', color: '#848484', marginTop: 14 },
  pageNumber: { textAlign: 'center', fontSize: 32, fontWeight: '700', color: '#6071e7', marginTop: 4 },
  pageTotal: { fontSize: 22, fontWeight: '500', color: '#848484' },
  pageCard: {
    marginHorizontal: 16, marginTop: 16,
    backgroundColor: '#fff', borderRadius: 10, minHeight: 150,
    padding: 16, alignItems: 'center',
  },
  pageCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  pageCardHeaderText: { fontSize: 14, fontWeight: '500', color: '#848484' },
  pageText: { fontSize: 24, fontWeight: '700', color: '#1f2937', textAlign: 'center', marginTop: 24, lineHeight: 32 },
  progressWrap: { paddingHorizontal: 16, marginTop: 20 },
  progressTrack: { height: 12, borderRadius: 45, backgroundColor: '#d9d9d9', overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 45, backgroundColor: '#6071e7' },
  progressLabels: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 9 },
  timeLabel: { fontSize: 20, fontWeight: '400', color: '#848484' },
  timeLabelActive: { color: '#6071e7' },
  controlsWrap: { marginTop: 24, alignItems: 'center' },
  controlsRow: { flexDirection: 'row', alignItems: 'center', gap: 32 },
  sideBtn: { width: 46, height: 46, alignItems: 'center', justifyContent: 'center' },
  playBtn: {
    width: 87, height: 87, borderRadius: 44,
    backgroundColor: '#dfe3ff',
    alignItems: 'center', justifyContent: 'center',
  },
  controlsLabelRow: { flexDirection: 'row', gap: 92, marginTop: 8 },
  controlsLabel: { fontSize: 12, fontWeight: '600', color: '#848484' },
  hint: { textAlign: 'center', fontSize: 16, fontWeight: '500', color: '#848484', marginTop: 'auto', marginBottom: 24 },
});
