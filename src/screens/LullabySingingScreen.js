import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import TitleSheetOverlay from '../components/TitleSheetOverlay';
import { useRecentItems } from '../store/RecentItemsContext';

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function LullabySingingScreen({ navigation }) {
  const { addItem } = useRecentItems();

  const [showTitleSheet, setShowTitleSheet] = useState(true);
  const [title, setTitle] = useState('자장가');

  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isRecording) return undefined;
    const id = setInterval(() => setElapsed((prev) => prev + 1), 1000);
    return () => clearInterval(id);
  }, [isRecording]);

  const toggleRecording = () => {
    setIsRecording((prev) => !prev);
  };

  const stopRecording = () => {
    setIsRecording(false);
  };

  const finishLullaby = () => {
    setIsRecording(false);
    addItem({ type: 'lullaby', title, meta: formatElapsed(elapsed) });
    navigation.navigate('Library');
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
          <TouchableOpacity onPress={finishLullaby}>
            <Text style={styles.doneLink}>완료</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.content}>
          <Text style={styles.instruction}>
            평소 아이에게 자장가를{'\n'}불러주는 말투로 녹음해주세요
          </Text>

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

          <View style={styles.btnStack}>
            <TouchableOpacity
              style={[styles.completeBtn, elapsed === 0 && styles.completeBtnDisabled]}
              onPress={finishLullaby}
              disabled={elapsed === 0}
            >
              <Text style={styles.completeText}>녹음 완료</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.stopBtn, !isRecording && styles.stopBtnDisabled]}
              onPress={isRecording ? stopRecording : undefined}
              disabled={!isRecording}
            >
              <Text style={styles.stopText}>녹음 종료</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>

      <TitleSheetOverlay
        visible={showTitleSheet}
        heading="자장가 제목을 작성해주세요."
        placeholder="자장자장자장가"
        onSubmit={(value) => {
          setTitle(value || '제목 없는 자장가');
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
  headerTitle: { fontSize: 18, fontWeight: '600', color: '#575757' },
  doneLink: { fontSize: 18, fontWeight: '600', color: '#6071e7' },
  content: { flex: 1, paddingHorizontal: 16, paddingTop: 24, justifyContent: 'space-between' },
  instruction: { fontSize: 24, fontWeight: '600', color: '#848484', textAlign: 'center', lineHeight: 32 },
  recordArea: { alignItems: 'center', justifyContent: 'center', gap: 24 },
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
  btnStack: { gap: 10, marginBottom: 32 },
  completeBtn: {
    height: 55, borderRadius: 8,
    backgroundColor: '#6071e7',
    alignItems: 'center', justifyContent: 'center',
  },
  completeBtnDisabled: { backgroundColor: '#b6bffc' },
  completeText: { fontSize: 20, fontWeight: '600', color: '#fff' },
  stopBtn: {
    height: 55, borderRadius: 8,
    backgroundColor: '#575757',
    alignItems: 'center', justifyContent: 'center',
  },
  stopBtnDisabled: { backgroundColor: '#d9d9d9' },
  stopText: { fontSize: 20, fontWeight: '600', color: '#fff' },
});
