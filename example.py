from supjav import supjav

class Example:
    def __init__(self):
        self.supjav = supjav()
    
    def run(self, url, path):
        self.supjav.run(url, path)


if __name__ == '__main__':
    app = Example()
    app.run('https://supjav.com/ja/398834.html', r'D:\DaikiVideos\supjav')