function MicButton({ onClick, isListening }) {
    return (
        <button onClick={onClick} style={{ fontSize: '2rem', padding: '1rem 2rem' }}>
            {isListening ? '🔴 Listening...' : '🎤 Tap to Shazam'}
        </button>
    )
}

export default MicButton