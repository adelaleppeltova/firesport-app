const ALWAYS_UPPERCASE_WORDS = new Set(["hzs"]);

function formatCategoryWord(word, isFirstWord) {
  const normalized = word.toLocaleLowerCase("cs-CZ");

  if (ALWAYS_UPPERCASE_WORDS.has(normalized)) {
    return normalized.toLocaleUpperCase("cs-CZ");
  }

  if (!isFirstWord) {
    return normalized;
  }

  return normalized.charAt(0).toLocaleUpperCase("cs-CZ") + normalized.slice(1);
}

export default function formatCategoryName(value) {
  if (!value) return value;

  let isFirstWord = true;

  return value.replace(/\p{L}+/gu, (word) => {
    const formattedWord = formatCategoryWord(word, isFirstWord);
    isFirstWord = false;
    return formattedWord;
  });
}
