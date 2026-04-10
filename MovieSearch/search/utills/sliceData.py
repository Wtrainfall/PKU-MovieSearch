class sliceData:
    def __init__(self, max_len=512):
        self.max_len = max_len

    def slice_script(self, script_path):
        slices = []
        current_slice = ""
        with open(script_path, 'r', encoding='utf-8') as f:
            for line in f:

                line = self.clean_special_chars(line)   

                line_lenth = len(line)
                if current_slice and len(current_slice) + line_lenth >= self.max_len:
                    current_slice += line
                    slices.append(current_slice)
                    current_slice = ""
                else:
                    current_slice += line

        if current_slice:
            slices.append(current_slice)
        
        return slices
    
    def clean_special_chars(self, text):
        """
        清理文本中的特殊字符
        """
        special_chars = [' ', '*']
        for char in special_chars:
            text = text.replace(char, '')
        
        return text

if __name__ == '__main__':
    script_path = 'movies\楚门的世界.txt'
    sd = sliceData()
    slices = sd.slice_script(script_path)
    for i, s in enumerate(slices):
        print(f"Slice {i}: {s}")