import { useCallback, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, StatusBar, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import BottomNav from '../components/BottomNav';
import { useRecentItems } from '../store/RecentItemsContext';
import { getLibrary } from '../api/client';

const FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'book', label: '동화책' },
  { key: 'lullaby', label: '자장가' },
];

export default function LibraryScreen({ navigation }) {
  const { items: localItems } = useRecentItems();

  const [libraryItems, setLibraryItems] = useState(null);
  const [isOffline, setIsOffline] = useState(false);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      getLibrary()
        .then((data) => {
          if (!cancelled) {
            setLibraryItems(data.map((entry) => ({
              id: entry.id,
              type: entry.kind,
              title: entry.title,
              meta: entry.status === 'ready' ? '재생 가능' : entry.status,
              playableUrl: entry.playable_url,
            })));
            setIsOffline(false);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setLibraryItems(null);
            setIsOffline(true);
          }
        });

      return () => {
        cancelled = true;
      };
    }, [])
  );

  const sourceItems = libraryItems ?? localItems;

  const searchedItems = sourceItems.filter((item) =>
    item.title.toLowerCase().includes(query.trim().toLowerCase())
  );

  const bookItems = searchedItems.filter((item) => item.type === 'book');
  const lullabyItems = searchedItems.filter((item) => item.type === 'lullaby');

  const showBooks = filter === 'all' || filter === 'book';
  const showLullabies = filter === 'all' || filter === 'lullaby';
  const hasAnyVisible = (showBooks && bookItems.length > 0) || (showLullabies && lullabyItems.length > 0);

  const openItem = (item) => {
    if (item.type === 'lullaby') {
      navigation.navigate('LullabyPlayback', { item });
    } else {
      navigation.navigate('BookPlayback', { item });
    }
  };

  const renderCard = (item) => (
    <View key={item.id} style={styles.itemCard}>
      <View style={styles.itemTextWrap}>
        <Text style={styles.itemTitle}>{item.title}</Text>
        <Text style={styles.itemMeta}>{item.meta}</Text>
      </View>
      <TouchableOpacity style={styles.playBtn} onPress={() => openItem(item)}>
        <Text style={styles.playBtnText}>재생</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>내 라이브러리</Text>
        </View>

        <View style={styles.searchWrap}>
          <Ionicons name="search" size={18} color="#adadad" style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
            placeholder="원하는 담음을 검색하세요."
            placeholderTextColor="#9f9f9f"
          />
        </View>

        {isOffline && (
          <View style={styles.offlineBanner}>
            <Ionicons name="cloud-offline-outline" size={14} color="#9f9f9f" />
            <Text style={styles.offlineText}>서버에 연결할 수 없어 기기에 저장된 목록을 보여드려요</Text>
          </View>
        )}

        <View style={styles.filterRow}>
          {FILTERS.map((item) => {
            const active = item.key === filter;
            return (
              <TouchableOpacity
                key={item.key}
                style={[styles.filterChip, active && styles.filterChipActive]}
                onPress={() => setFilter(item.key)}
              >
                <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
                  {item.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <ScrollView contentContainerStyle={styles.list}>
          {hasAnyVisible ? (
            <>
              {showBooks && bookItems.length > 0 && (
                <View style={styles.section}>
                  <View style={styles.sectionHeader}>
                    <Ionicons name="add-circle-outline" size={18} color="#1f2937" />
                    <Text style={styles.sectionTitle}>동화책</Text>
                  </View>
                  <View style={styles.sectionList}>
                    {bookItems.map(renderCard)}
                  </View>
                </View>
              )}

              {showLullabies && lullabyItems.length > 0 && (
                <View style={styles.section}>
                  <View style={styles.sectionHeader}>
                    <Ionicons name="moon-outline" size={18} color="#1f2937" />
                    <Text style={styles.sectionTitle}>자장가</Text>
                  </View>
                  <View style={styles.sectionList}>
                    {lullabyItems.map(renderCard)}
                  </View>
                </View>
              )}
            </>
          ) : (
            <View style={styles.emptyWrap}>
              <Ionicons name="book-outline" size={40} color="#c4ccff" />
              <Text style={styles.emptyText}>아직 담은 동화책이 없어요</Text>
            </View>
          )}
        </ScrollView>

        <BottomNav navigation={navigation} active="library" />
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f6ff' },
  safe: { flex: 1 },
  header: { height: 101, paddingTop: 44, backgroundColor: '#fff', justifyContent: 'center', paddingHorizontal: 21 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: '#353535' },
  searchWrap: {
    marginHorizontal: 16, marginTop: 16,
    height: 50, borderRadius: 50,
    borderWidth: 1, borderColor: '#adadad', backgroundColor: '#fcfcfc',
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, gap: 8,
  },
  searchIcon: {},
  searchInput: { flex: 1, fontSize: 15, color: '#353535' },
  offlineBanner: {
    marginHorizontal: 16, marginTop: 10,
    flexDirection: 'row', alignItems: 'center', gap: 6,
  },
  offlineText: { fontSize: 11.5, color: '#9f9f9f' },
  filterRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, marginTop: 14 },
  filterChip: {
    paddingHorizontal: 14, paddingVertical: 7, borderRadius: 999,
    borderWidth: 1, borderColor: '#ededed', backgroundColor: '#fff',
  },
  filterChipActive: { backgroundColor: '#6071e7', borderColor: '#6071e7' },
  filterChipText: { fontSize: 13, fontWeight: '500', color: '#1f2937' },
  filterChipTextActive: { color: '#fff' },
  list: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 16 },
  section: { marginBottom: 20 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  sectionTitle: { fontSize: 20, fontWeight: '700', color: '#1f2937' },
  sectionList: { gap: 12 },
  itemCard: {
    backgroundColor: '#fff', borderRadius: 15,
    borderWidth: 1, borderColor: '#dfdfdf',
    padding: 16,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  itemTextWrap: { flex: 1, marginRight: 12 },
  itemTitle: { fontSize: 16, fontWeight: '600', color: '#1f2937' },
  itemMeta: { fontSize: 12, fontWeight: '400', color: '#1f2937', opacity: 0.6, marginTop: 4 },
  playBtn: { backgroundColor: '#6071e7', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 6 },
  playBtnText: { fontSize: 14, fontWeight: '500', color: '#fff' },
  emptyWrap: { alignItems: 'center', justifyContent: 'center', paddingVertical: 60, gap: 12 },
  emptyText: { fontSize: 15, fontWeight: '500', color: '#9f9f9f' },
});
