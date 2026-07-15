import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import TitleSheetOverlay from '../components/TitleSheetOverlay';
import { useRecentItems } from '../store/RecentItemsContext';

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function BookReadingScreen({ navigation }) {
  const { addItem } = useRecentItems();

  const [showTitleSheet, setShowTitleSheet] = useState(true);
  const [title, setTitle] = useState('동화책');

  const [pages, setPages] = useState([1]);
  const [currentPage, setCurrentPage] = useState(1);
  const [recordedPages, setRecordedPages] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isRecording) return undefined;
    const id = setInterval(() => setElapsed((prev) => prev + 1), 1000);
    return () => clearInterval(id);
  }, [isRecording]);

  const toggleRecording = () => {
    if (isRecording) {
      setIsRecording(false);
      setRecordedPages((prev) => (prev.includes(currentPage) ? prev : [...prev, currentPage]));
    } else {
      setIsRecording(true);
    }
  };

  const switchPage = (page) => {
    setIsRecording(false);
    setElapsed(0);
    setCurrentPage(page);
  };

  const addPage = () => {
    if (isRecording) {
      setIsRecording(false);
      setRecordedPages((prev) => (prev.includes(currentPage) ? prev : [...prev, currentPage]));
    }
    const nextPage = pages.length + 1;
    setPages((prev) => [...prev, nextPage]);
    setElapsed(0);
    setCurrentPage(nextPage);
  };

  const finishBook = () => {
    setIsRecording(false);
    addItem({ type: 'book', title, meta: `${pages.length}페이지` });
    navigation.navigate('Library');
  };

  const goPrevPage = () => {
    const idx = pages.indexOf(currentPage);
    if (idx > 0) switchPage(pages[idx - 1]);
  };

  const goNextPage = () => {
    const idx = pages.indexOf(currentPage);
    if (idx < pages.length - 1) switchPage(pages[idx + 1]);
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
          <View style={styles.headerSide} />
        </View>

        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.instruction}>
            책을 펴서 평소 아이에게{'\n'}말하는 말투로 읽어주세요
          </Text>

          <View style={styles.pageBadgeWrap}>
            <View style={styles.pageBadge}>
              <Text style={styles.pageBadgeText}>페이지 {currentPage}</Text>
            </View>
          </View>

          <View style={styles.recordArea}>
            <Text style={styles.timer}>
              {isRecording ? (
                <>
                  {formatElapsed(elapsed).slice(0, 2)}:
                  <Text style={styles.timerActive}>{formatElapsed(elapsed).slice(3)}</Text>
                </>
              ) : (
                formatElapsed(elapsed)
              )}
            </Text>

            <TouchableOpacity style={styles.circleOuter} onPress={toggleRecording}>
              <View style={styles.circleInner}>
                <Ionicons
                  name={isRecording ? 'pause' : 'mic'}
                  size={isRecording ? 40 : 44}
                  color="#6071e7"
                />
              </View>
            </TouchableOpacity>

            <Text style={styles.hint}>{isRecording ? '듣고 있어요..' : '누르면 녹음이 시작돼요'}</Text>
          </View>

          {pages.length > 1 && (
            <View style={styles.pagerRow}>
              <TouchableOpacity onPress={goPrevPage}>
                <Ionicons name="chevron-back" size={24} color="#6071e7" />
              </TouchableOpacity>
              {pages.map((page) => {
                const isCurrent = page === currentPage;
                return (
                  <TouchableOpacity
                    key={page}
                    style={[styles.pagePill, isCurrent && styles.pagePillCurrent]}
                    onPress={() => switchPage(page)}
                  >
                    <Text style={styles.pagePillText}>{page}</Text>
                  </TouchableOpacity>
                );
              })}
              <TouchableOpacity onPress={goNextPage}>
                <Ionicons name="chevron-forward" size={24} color="#6071e7" />
              </TouchableOpacity>
            </View>
          )}

          <TouchableOpacity style={styles.addPageBtn} onPress={addPage}>
            <Text style={styles.addPageText}>페이지 추가하기</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.doneBtn} onPress={finishBook}>
            <Text style={styles.doneText}>다 읽었어요</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>

      <TitleSheetOverlay
        visible={showTitleSheet}
        heading="동화책 제목을 작성해주세요."
        placeholder="돼지 삼형제"
        onSubmit={(value) => {
          setTitle(value || '제목 없는 동화책');
          setShowTitleSheet(false);
        }}
        onSkip={() => navigation.navigate('Dashboard')}
      />
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
  headerTitle: { fontSize: 18, fontWeight: '500', color: '#353535' },
  content: { paddingHorizontal: 16, paddingTop: 24, paddingBottom: 32 },
  instruction: { fontSize: 24, fontWeight: '600', color: '#848484', textAlign: 'center', lineHeight: 32 },
  pageBadgeWrap: { alignItems: 'center', marginTop: 20 },
  pageBadge: {
    backgroundColor: '#6071e7', borderRadius: 45,
    height: 30, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center',
  },
  pageBadgeText: { fontSize: 18, fontWeight: '600', color: '#fff' },
  recordArea: { alignItems: 'center', justifyContent: 'center', gap: 24, marginTop: 40 },
  timer: { fontSize: 20, fontWeight: '500', color: '#848484' },
  timerActive: { fontWeight: '600', color: '#6071e7' },
  circleOuter: {
    width: 162, height: 162, borderRadius: 81,
    backgroundColor: '#eceeff', alignItems: 'center', justifyContent: 'center',
  },
  circleInner: {
    width: 132, height: 132, borderRadius: 66,
    backgroundColor: '#dfe3ff', alignItems: 'center', justifyContent: 'center',
  },
  hint: { fontSize: 20, fontWeight: '500', color: '#848484' },
  pagerRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    marginTop: 40,
  },
  pagePill: {
    width: 30, height: 30, borderRadius: 45,
    backgroundColor: '#6071e7', alignItems: 'center', justifyContent: 'center',
  },
  pagePillCurrent: { backgroundColor: '#d5daff', borderWidth: 1, borderColor: '#96a3ff' },
  pagePillText: { fontSize: 18, fontWeight: '600', color: '#fff' },
  addPageBtn: {
    marginTop: 32, height: 55, borderRadius: 8,
    backgroundColor: '#edefff', borderWidth: 1, borderColor: '#96a3ff', borderStyle: 'dashed',
    alignItems: 'center', justifyContent: 'center',
  },
  addPageText: { fontSize: 20, fontWeight: '600', color: '#6071e7' },
  doneBtn: {
    marginTop: 12, height: 55, borderRadius: 8,
    backgroundColor: '#6071e7',
    alignItems: 'center', justifyContent: 'center',
  },
  doneText: { fontSize: 20, fontWeight: '600', color: '#fff' },
});
