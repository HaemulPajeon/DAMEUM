import { TouchableOpacity, StyleSheet, Platform } from 'react-native';

export default function HomeIndicator({ onPress, light = false }) {
    if (Platform.OS !== 'web') return null;

    return (
        <TouchableOpacity
            style={[styles.bar, light ? styles.barLight : styles.barDark]}
            onPress={onPress}
            accessibilityLabel="홈으로 이동"
        />
    );
}

const styles = StyleSheet.create({
    bar: {
        position: 'absolute',
        bottom: 8,
        left: '50%',
        marginLeft: -67,
        width: 134,
        height: 5,
        borderRadius: 3,
        zIndex: 100,
    },
    barDark: { backgroundColor: '#232244', opacity: 0.85 },
    barLight: { backgroundColor: 'rgba(255,255,255,0.9)' },
});