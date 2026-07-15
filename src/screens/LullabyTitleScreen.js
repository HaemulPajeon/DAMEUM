import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function LullabyTitleScreen({ navigation }) {
  const [title, setTitle] = useState('');

  const goToSinging = (lullabyTitle) => {
    navigation.navigate('LullabySinging', { title: lullabyTitle || '제목 없는 자장가' });
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
        <View style={styles.sheet}>
          <View style={styles.dragHandle} />
          <Text style={styles.heading}>자장가 제목을 작성해주세요.</Text>
          <Text style={styles.subLabel}>제목을 지어주세요.</Text>
          <TextInput
            style={styles.input}
            value={title}
            onChangeText={setTitle}
            placeholder="자장자장자장가"
            placeholderTextColor="#bdbdbd"
          />

          <View style={styles.btnRow}>
            <TouchableOpacity style={styles.secondaryBtn} onPress={() => goToSinging('')}>
              <Text style={styles.secondaryText}>다음에</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.primaryBtn} onPress={() => goToSinging(title.trim())}>
              <Text style={styles.primaryText}>작성했어요</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f6ff' },
  safe: { flex: 1, justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 17,
    paddingTop: 7,
    paddingBottom: 32,
  },
  dragHandle: {
    alignSelf: 'center',
    width: 95, height: 4, borderRadius: 45,
    backgroundColor: '#d9d9d9',
    marginBottom: 40,
  },
  heading: { fontSize: 22, fontWeight: '700', color: '#353535' },
  subLabel: { fontSize: 16, fontWeight: '400', color: '#848484', marginTop: 12 },
  input: {
    marginTop: 8,
    height: 57, borderRadius: 10,
    borderWidth: 1, borderColor: '#bdbdbd',
    backgroundColor: '#f2f2f2',
    paddingHorizontal: 16,
    fontSize: 16, color: '#353535',
  },
  btnRow: { flexDirection: 'row', gap: 8, marginTop: 32 },
  secondaryBtn: {
    flex: 1, height: 55, borderRadius: 8,
    backgroundColor: '#f2f2f2',
    alignItems: 'center', justifyContent: 'center',
  },
  secondaryText: { fontSize: 18, fontWeight: '500', color: '#353535' },
  primaryBtn: {
    flex: 1, height: 55, borderRadius: 8,
    backgroundColor: '#6071e7',
    alignItems: 'center', justifyContent: 'center',
  },
  primaryText: { fontSize: 18, fontWeight: '600', color: '#fff' },
});
