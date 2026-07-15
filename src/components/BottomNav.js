import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const NAV_ITEMS = [
  { key: 'home', label: '홈', icon: 'home', route: 'Dashboard' },
  { key: 'library', label: '라이브러리', icon: 'grid', route: 'Library' },
  { key: 'book', label: '동화책', icon: 'add-circle', route: 'BookReading' },
  { key: 'lullaby', label: '자장가', icon: 'moon', route: 'LullabySinging' },
  { key: 'profile', label: '프로필', icon: 'person', route: 'Profile' },
];

export default function BottomNav({ navigation, active = 'home' }) {
  return (
    <View style={styles.bottomNav}>
      {NAV_ITEMS.map((item) => {
        const isActive = item.key === active;
        return (
          <TouchableOpacity
            key={item.key}
            style={styles.navItem}
            onPress={() => {
              if (item.route) navigation.navigate(item.route);
            }}
          >
            <Ionicons name={item.icon} size={21} color={isActive ? '#6071e7' : '#575757'} />
            <Text style={[styles.navLabel, isActive && styles.navLabelActive]}>{item.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
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
