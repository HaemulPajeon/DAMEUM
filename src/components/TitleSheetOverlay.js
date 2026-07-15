import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet } from 'react-native';

export default function TitleSheetOverlay({ visible, heading, placeholder, onSubmit, onSkip }) {
  const [title, setTitle] = useState('');

  if (!visible) return null;

  return (
    <View style={styles.overlay}>
      <View style={styles.backdrop} />
      <View style={styles.sheet}>
        <View style={styles.dragHandle} />
        <Text style={styles.heading}>{heading}</Text>
        <Text style={styles.subLabel}>제목을 지어주세요.</Text>
        <TextInput
          style={styles.input}
          value={title}
          onChangeText={setTitle}
          placeholder={placeholder}
          placeholderTextColor="#bdbdbd"
        />
        <View style={styles.btnRow}>
          <TouchableOpacity style={styles.secondaryBtn} onPress={onSkip}>
            <Text style={styles.secondaryText}>다음에</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.primaryBtn} onPress={() => onSubmit(title.trim())}>
            <Text style={styles.primaryText}>작성했어요</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    justifyContent: 'flex-end',
    zIndex: 100,
  },
  backdrop: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
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
