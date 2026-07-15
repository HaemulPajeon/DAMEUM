import { useEffect } from 'react';
import { View, StyleSheet, Platform } from 'react-native';

export default function PhoneFrame({ children }) {
    useEffect(() => {
        if (Platform.OS !== 'web') return;
        if (document.getElementById('hide-scrollbar-style')) return;
        const style = document.createElement('style');
        style.id = 'hide-scrollbar-style';
        style.innerHTML = `
      * { scrollbar-width: none; -ms-overflow-style: none; }
      *::-webkit-scrollbar { display: none; width: 0; height: 0; }
    `;
        document.head.appendChild(style);
    }, []);

    if (Platform.OS !== 'web') {
        return children;
    }

    return (
        <View style={styles.stage}>
            <View style={styles.phone}>
                <View style={styles.buttonMute} />
                <View style={styles.buttonVolUp} />
                <View style={styles.buttonVolDown} />
                <View style={styles.buttonPower} />

                <View style={styles.screen}>{children}</View>

                <View style={styles.notch}>
                    <View style={styles.lens} />
                </View>
            </View>
        </View>
    );
}

const FRAME_COLOR = '#c7bcd6';

const styles = StyleSheet.create({
    stage: {
        flex: 1,
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#3a3a3a',
    },
    phone: {
        width: 390,
        height: 844,
        backgroundColor: FRAME_COLOR,
        borderRadius: 62,
        padding: 12,
        position: 'relative',
        boxShadow: '0 40px 90px rgba(0,0,0,0.55)',
    },
    screen: {
        flex: 1,
        borderRadius: 52,
        overflow: 'hidden',
        backgroundColor: '#000',
        position: 'relative',
    },
    notch: {
        position: 'absolute',
        top: 24,
        left: '50%',
        marginLeft: -63,
        width: 126,
        height: 37,
        backgroundColor: '#050505',
        borderRadius: 22,
        zIndex: 100,
        alignItems: 'flex-end',
        justifyContent: 'center',
        paddingRight: 12,
    },
    lens: {
        width: 11,
        height: 11,
        borderRadius: 6,
        backgroundColor: '#1a2a4a',
    },
    buttonMute: {
        position: 'absolute',
        left: -3,
        top: 118,
        width: 3,
        height: 28,
        backgroundColor: FRAME_COLOR,
        borderRadius: 2,
    },
    buttonVolUp: {
        position: 'absolute',
        left: -3,
        top: 168,
        width: 3,
        height: 58,
        backgroundColor: FRAME_COLOR,
        borderRadius: 2,
    },
    buttonVolDown: {
        position: 'absolute',
        left: -3,
        top: 238,
        width: 3,
        height: 58,
        backgroundColor: FRAME_COLOR,
        borderRadius: 2,
    },
    buttonPower: {
        position: 'absolute',
        right: -3,
        top: 200,
        width: 3,
        height: 90,
        backgroundColor: FRAME_COLOR,
        borderRadius: 2,
    },
});