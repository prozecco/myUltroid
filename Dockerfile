FROM theteamultroid/ultroid:main

# Set timezone
ENV TZ=Asia/Bangkok
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set workdir
WORKDIR "/root/TeamUltroid"

# Copy modified files
COPY . .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r resources/startup/optional-requirements.txt

# Start the bot
CMD ["python3", "-m", "pyUltroid"]
