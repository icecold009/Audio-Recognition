function ResultCard({ result }) {
    if (!result) return null

    if (result.status === 'error' || result.status === 'rate_limited') {
        return <p style={{ color: 'red' }}>{result.error}</p>
    }

    return (
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
            {result.image && (
                <img
                    src={result.image}
                    alt="Album cover"
                    style={{ width: '200px', height: '200px', borderRadius: '12px', marginBottom: '1rem' }}
                />
            )}
            <h2>{result.title}</h2>
            <p>{result.artist}</p>
            {result.album && <p style={{ color: 'gray' }}>{result.album}</p>}
        </div>
    )
}

export default ResultCard