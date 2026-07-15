import { TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function BackButton({ onPress, dark = false }) {
    return (
        <TouchableOpacity style={styles.btn} onPress={onPress} accessibilityLabel="뒤로가기">
            <Ionicons name="chevron-back" size={22} color={dark ? '#232244' : '#fff'} />
        </TouchableOpacity>
    );
}

const styles = StyleSheet.create({
    btn: {
        position: 'absolute',
        top: 54,
        left: 16,
        width: 34,
        height: 34,
        borderRadius: 17,
        backgroundColor: 'rgba(0,0,0,0.15)',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 60,
    },
});